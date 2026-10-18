#!/usr/bin/env bash
# Crea (o completa, es idempotente) la infraestructura de la Entrega 1:
#   roles de IAM -> security group + RDS PostgreSQL -> aplicación y entorno Beanstalk
#   (Load balanced, ASG 3-6, health check /health) -> regla RDS <- instancias.
# El entorno nace con la aplicación de ejemplo de AWS: el despliegue del código se hace a mano.
#
#   ./scripts/infra-up.sh --check   solo lectura: valida credenciales, plataforma y qué existe ya
#   ./scripts/infra-up.sh           crea lo que falte
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/infra-common.sh"

CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

require_cli
VPC="$(default_vpc)"; [ -n "$VPC" ] && [ "$VPC" != None ] || die "No hay VPC por defecto en $AWS_DEFAULT_REGION"
SUBNETS="$(subnet_ids "$VPC")"; [ -n "$SUBNETS" ] || die "No se encontraron subredes"
PLATFORM="$(aws elasticbeanstalk list-available-solution-stacks \
  --query "SolutionStacks[?contains(@,'Amazon Linux 2023') && ends_with(@,'running Python ${PYTHON_VERSION}')]|[0]" --output text)"
[ -n "$PLATFORM" ] && [ "$PLATFORM" != None ] || die "No hay plataforma Beanstalk para Python $PYTHON_VERSION"
log "VPC $VPC · subredes $SUBNETS"
log "Plataforma: $PLATFORM"

# ---- estado actual ------------------------------------------------------------------------
role_exists()  { aws iam get-role --role-name "$1" >/dev/null 2>&1; }
db_status()    { aws rds describe-db-instances --db-instance-identifier "$DB_ID" --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || true; }
log "Rol de servicio ($SERVICE_ROLE):  $(role_exists "$SERVICE_ROLE" && echo existe || echo 'falta')"
log "Rol de instancias ($INSTANCE_ROLE): $(role_exists "$INSTANCE_ROLE" && echo existe || echo 'falta')"
log "Security group $RDS_SG_NAME:        $([ -n "$(rds_sg_id "$VPC")" ] && echo existe || echo 'falta')"
log "RDS $DB_ID:                         $(db_status | grep . || echo 'no existe')"
log "Entorno $ENV_NAME:                  $(env_status | grep . || echo 'no existe')"
$CHECK_ONLY && { log "--check: no se creó nada"; exit 0; }

# ---- 1. Secretos (antes de tocar nada: si faltan y la infra existe, aborta) ----------------------------------------------------------------------------
if [ -f "$SECRETS_FILE" ]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
fi
if [ ! -f "$SECRETS_FILE" ] && { [ -n "$(db_status)" ] || [ -n "$(env_status)" ]; }; then
  die "Ya existe la base o el entorno pero falta $SECRETS_FILE: generar una contraseña nueva no coincidiría con la real. Corre infra-down.sh primero, o crea el archivo con DB_PASSWORD y STATIC_TOKEN."
fi
if [ -z "${DB_PASSWORD:-}" ] || [ -z "${STATIC_TOKEN:-}" ]; then
  command -v openssl >/dev/null || die "Se necesita openssl para generar los secretos"
  DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"   # solo [0-9a-f]: no necesita escapes en URLs
  STATIC_TOKEN="${STATIC_TOKEN:-$(openssl rand -hex 24)}"
  umask 077
  printf 'DB_PASSWORD=%s\nSTATIC_TOKEN=%s\n' "$DB_PASSWORD" "$STATIC_TOKEN" > "$SECRETS_FILE"
  log "Secretos generados en $SECRETS_FILE"
fi

# ---- 2. IAM ---------------------------------------------------------------------------------
trust() { printf '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"%s"},"Action":"sts:AssumeRole"}]}' "$1"; }
attach() { aws iam attach-role-policy --role-name "$1" --policy-arn "$2"; }

if ! role_exists "$SERVICE_ROLE"; then
  log "Creando rol de servicio $SERVICE_ROLE"
  aws iam create-role --role-name "$SERVICE_ROLE" --assume-role-policy-document "$(trust elasticbeanstalk.amazonaws.com)" >/dev/null
fi
attach "$SERVICE_ROLE" arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth
attach "$SERVICE_ROLE" arn:aws:iam::aws:policy/AWSElasticBeanstalkManagedUpdatesCustomerRolePolicy

if ! role_exists "$INSTANCE_ROLE"; then
  log "Creando rol de instancias $INSTANCE_ROLE"
  aws iam create-role --role-name "$INSTANCE_ROLE" --assume-role-policy-document "$(trust ec2.amazonaws.com)" >/dev/null
fi
for p in AWSElasticBeanstalkWebTier AWSElasticBeanstalkWorkerTier AWSElasticBeanstalkMulticontainerDocker; do
  attach "$INSTANCE_ROLE" "arn:aws:iam::aws:policy/$p"
done
if ! aws iam get-instance-profile --instance-profile-name "$INSTANCE_ROLE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$INSTANCE_ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$INSTANCE_ROLE" --role-name "$INSTANCE_ROLE"
  log "Instance profile creado; esperando a que IAM lo propague"; sleep 15
fi

# ---- 3. Security group de la base y RDS ----------------------------------------------------
RDS_SG="$(rds_sg_id "$VPC")"
if [ -z "$RDS_SG" ]; then
  log "Creando security group $RDS_SG_NAME"
  RDS_SG="$(aws ec2 create-security-group --group-name "$RDS_SG_NAME" --vpc-id "$VPC" \
    --description "Acceso a RDS desde las instancias de Beanstalk" --query GroupId --output text)"
fi

if [ -z "$(db_status)" ]; then
  log "Creando RDS $DB_ID (tarda varios minutos)"
  aws rds create-db-instance \
    --db-instance-identifier "$DB_ID" --engine postgres \
    --db-instance-class "$DB_CLASS" --allocated-storage "$DB_STORAGE_GB" \
    --db-name "$DB_NAME" --master-username "$DB_USER" --master-user-password "$DB_PASSWORD" \
    --vpc-security-group-ids "$RDS_SG" \
    --no-publicly-accessible --no-multi-az --storage-encrypted \
    --backup-retention-period 0 --no-deletion-protection >/dev/null
fi
log "Esperando a que RDS esté disponible..."
aws rds wait db-instance-available --db-instance-identifier "$DB_ID"
DB_HOST="$(aws rds describe-db-instances --db-instance-identifier "$DB_ID" --query 'DBInstances[0].Endpoint.Address' --output text)"
log "RDS lista: $DB_HOST"

# ---- 4. Beanstalk ---------------------------------------------------------------------------
if ! aws elasticbeanstalk describe-applications --application-names "$APP_NAME" --query 'Applications[0].ApplicationName' --output text 2>/dev/null | grep -qx "$APP_NAME"; then
  log "Creando aplicación $APP_NAME"
  aws elasticbeanstalk create-application --application-name "$APP_NAME" >/dev/null
fi

if [ -z "$(env_status)" ]; then
  log "Creando entorno $ENV_NAME (Load balanced, $MIN_SIZE-$MAX_SIZE instancias, aplicación de ejemplo)"
  OPTS="$(mktemp)"; trap 'rm -f "$OPTS"' EXIT
  cat > "$OPTS" <<JSON
[
 {"Namespace":"aws:autoscaling:launchconfiguration","OptionName":"IamInstanceProfile","Value":"$INSTANCE_ROLE"},
 {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"ServiceRole","Value":"$SERVICE_ROLE"},
 {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"EnvironmentType","Value":"LoadBalanced"},
 {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"LoadBalancerType","Value":"application"},
 {"Namespace":"aws:autoscaling:asg","OptionName":"MinSize","Value":"$MIN_SIZE"},
 {"Namespace":"aws:autoscaling:asg","OptionName":"MaxSize","Value":"$MAX_SIZE"},
 {"Namespace":"aws:ec2:instances","OptionName":"InstanceTypes","Value":"$INSTANCE_TYPES"},
 {"Namespace":"aws:ec2:vpc","OptionName":"VPCId","Value":"$VPC"},
 {"Namespace":"aws:ec2:vpc","OptionName":"Subnets","Value":"$SUBNETS"},
 {"Namespace":"aws:ec2:vpc","OptionName":"ELBSubnets","Value":"$SUBNETS"},
 {"Namespace":"aws:ec2:vpc","OptionName":"ELBScheme","Value":"public"},
 {"Namespace":"aws:ec2:vpc","OptionName":"AssociatePublicIpAddress","Value":"true"},
 {"Namespace":"aws:elasticbeanstalk:environment:process:default","OptionName":"HealthCheckPath","Value":"/health"},
 {"Namespace":"aws:elasticbeanstalk:healthreporting:system","OptionName":"SystemType","Value":"enhanced"},
 {"Namespace":"aws:elasticbeanstalk:application:environment","OptionName":"DATABASE_URL","Value":"postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:5432/$DB_NAME"},
 {"Namespace":"aws:elasticbeanstalk:application:environment","OptionName":"STATIC_TOKEN","Value":"$STATIC_TOKEN"}
]
JSON
  aws elasticbeanstalk create-environment --application-name "$APP_NAME" --environment-name "$ENV_NAME" \
    --solution-stack-name "$PLATFORM" --option-settings "file://$OPTS" >/dev/null
fi
log "Esperando a que el entorno esté Ready (suele tardar 5-10 min)..."
wait_env Ready

# ---- 5. RDS <- instancias de Beanstalk -------------------------------------------------------
INST_SG="$(aws ec2 describe-instances \
  --filters "Name=tag:elasticbeanstalk:environment-name,Values=$ENV_NAME" Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)"
[ -n "$INST_SG" ] && [ "$INST_SG" != None ] || die "No se encontró el security group de las instancias"
if aws ec2 authorize-security-group-ingress --group-id "$RDS_SG" --protocol tcp --port 5432 --source-group "$INST_SG" >/dev/null 2>&1; then
  log "Regla agregada: $RDS_SG acepta 5432 desde $INST_SG"
else
  log "La regla 5432 desde $INST_SG ya existía"
fi

ENV_URL="http://$(aws elasticbeanstalk describe-environments --application-name "$APP_NAME" --environment-names "$ENV_NAME" \
  --query 'Environments[?Status!=`Terminated`]|[0].CNAME' --output text)"
cat <<EOM

Infraestructura lista.
  URL del entorno : $ENV_URL
  Endpoint de RDS : $DB_HOST
  Credenciales    : $SECRETS_FILE   (DB_PASSWORD y STATIC_TOKEN; no se suben a git)

Siguiente paso, a mano: Beanstalk -> Upload and deploy con el zip del repo (git archive -o deploy.zip HEAD).
El hook .ebextensions crea las tablas al desplegar. Luego prueba:  curl $ENV_URL/ping
EOM
