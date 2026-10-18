#!/usr/bin/env bash
# Borra TODO lo que creó infra-up.sh: entorno Beanstalk, aplicación, RDS (sin snapshot final: los
# datos se pierden) y el security group de la base. Los roles de IAM se conservan (son gratis y
# los reutiliza infra-up.sh).
#
#   ./scripts/infra-down.sh        pide confirmación escribiendo el nombre del entorno
#   ./scripts/infra-down.sh --yes  sin preguntar
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/infra-common.sh"

require_cli
VPC="$(default_vpc)"

if [ "${1:-}" != "--yes" ]; then
  warn "Se va a borrar el entorno '$ENV_NAME', la aplicación '$APP_NAME' y la base '$DB_ID' SIN snapshot (datos perdidos)."
  read -r -p "Escribe el nombre del entorno para confirmar: " ans
  [ "$ans" = "$ENV_NAME" ] || die "Cancelado"
fi

if [ -n "$(env_status)" ]; then
  log "Terminando el entorno $ENV_NAME..."
  aws elasticbeanstalk terminate-environment --environment-name "$ENV_NAME" >/dev/null
  wait_env Terminated
else
  log "El entorno no existe"
fi

if aws elasticbeanstalk describe-applications --application-names "$APP_NAME" --query 'Applications[0].ApplicationName' --output text 2>/dev/null | grep -qx "$APP_NAME"; then
  log "Borrando la aplicación $APP_NAME y sus versiones"
  aws elasticbeanstalk delete-application --application-name "$APP_NAME" --terminate-env-by-force >/dev/null
fi

if aws rds describe-db-instances --db-instance-identifier "$DB_ID" >/dev/null 2>&1; then
  log "Borrando RDS $DB_ID (tarda unos minutos)"
  aws rds delete-db-instance --db-instance-identifier "$DB_ID" --skip-final-snapshot --delete-automated-backups >/dev/null
  aws rds wait db-instance-deleted --db-instance-identifier "$DB_ID"
else
  log "La base no existe"
fi

SG="$(rds_sg_id "$VPC")"
if [ -n "$SG" ]; then
  log "Borrando security group $RDS_SG_NAME"
  # El grupo de las instancias se elimina con el entorno; si algo aún lo referencia, reintenta.
  for _ in 1 2 3 4 5 6; do
    aws ec2 delete-security-group --group-id "$SG" 2>/dev/null && break || sleep 15
  done
fi

rm -f "$SECRETS_FILE" && log "Credenciales locales eliminadas"
log "Listo."
