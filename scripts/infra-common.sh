# Variables y utilidades compartidas por infra-up.sh e infra-down.sh. Se usa con `source`.
# Todo se puede sobreescribir por variable de entorno, p. ej.:  DB_CLASS=db.t3.micro ./scripts/infra-up.sh

export AWS_PROFILE="${AWS_PROFILE:-maestria}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_PAGER=""

APP_NAME="${APP_NAME:-blacklist-api}"
ENV_NAME="${ENV_NAME:-Blacklist-api-env}"
PYTHON_VERSION="${PYTHON_VERSION:-3.14}"
MIN_SIZE="${MIN_SIZE:-3}"
MAX_SIZE="${MAX_SIZE:-6}"
INSTANCE_TYPES="${INSTANCE_TYPES:-t3.micro,t3.small}"

DB_ID="${DB_ID:-blacklist-db}"
DB_NAME="${DB_NAME:-blacklist}"
DB_USER="${DB_USER:-postgres}"
DB_CLASS="${DB_CLASS:-db.t4g.micro}"
DB_STORAGE_GB="${DB_STORAGE_GB:-20}"
RDS_SG_NAME="${RDS_SG_NAME:-rds-blacklist-sg}"

SERVICE_ROLE="${SERVICE_ROLE:-aws-elasticbeanstalk-service-role}"
INSTANCE_ROLE="${INSTANCE_ROLE:-aws-elasticbeanstalk-ec2-role}"

# Credenciales generadas: quedan aquí, fuera de git (ver .gitignore), con permisos 600.
SECRETS_FILE="${SECRETS_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.infra-secrets}"

log()  { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

require_cli() {
  command -v aws >/dev/null || die "No se encontró el AWS CLI"
  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
    || die "Credenciales inválidas para el perfil '$AWS_PROFILE' (prueba: aws sts get-caller-identity --profile $AWS_PROFILE)"
  log "Cuenta $ACCOUNT_ID · perfil $AWS_PROFILE · región $AWS_DEFAULT_REGION"
}

default_vpc() {
  aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text
}

# Subredes de la VPC por defecto. En us-east-1 se omite la zona 1e: no soporta todos los
# tipos t3 y Beanstalk falla si se la das. Se puede fijar con SUBNET_IDS="subnet-a,subnet-b".
subnet_ids() {
  if [ -n "${SUBNET_IDS:-}" ]; then echo "$SUBNET_IDS"; return; fi
  aws ec2 describe-subnets --filters "Name=vpc-id,Values=$1" \
    --query "Subnets[?AvailabilityZone!='${AWS_DEFAULT_REGION}e'].SubnetId" --output text | tr '\t' ','
}

rds_sg_id() {
  aws ec2 describe-security-groups --filters "Name=group-name,Values=$RDS_SG_NAME" "Name=vpc-id,Values=$1" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null | sed 's/^None$//'
}

env_status() {
  aws elasticbeanstalk describe-environments --application-name "$APP_NAME" --environment-names "$ENV_NAME" \
    --query 'Environments[?Status!=`Terminated`]|[0].Status' --output text 2>/dev/null | sed 's/^None$//'
}

wait_env() {  # wait_env <estado>
  local want="$1" s
  for _ in $(seq 1 120); do
    s="$(env_status)"
    [ "$s" = "$want" ] && return 0
    [ -z "$s" ] && [ "$want" = "Terminated" ] && return 0
    sleep 15
  done
  die "Tiempo agotado esperando que el entorno pase a '$want' (último estado: ${s:-ninguno})"
}
