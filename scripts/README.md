# Scripts de infraestructura (AWS CLI)

Recrean la infraestructura de la Entrega 1. El despliegue del código se hace a mano.

| Script | Qué hace |
|---|---|
| `infra-up.sh --check` | Solo lectura: valida credenciales, plataforma y qué recursos existen |
| `infra-up.sh` | Crea lo que falte: roles IAM, security group, RDS PostgreSQL, aplicación y entorno Beanstalk (Load balanced, 3–6 instancias, health check `/health`) y la regla RDS ← instancias |
| `infra-down.sh` | Borra entorno, aplicación, RDS (sin snapshot) y security group. Conserva los roles de IAM |

Requisitos: AWS CLI v2, `openssl` y un perfil con permisos de administrador (por defecto `maestria`,
región `us-east-1`; se cambia con `AWS_PROFILE` / `AWS_DEFAULT_REGION`).

```bash
./scripts/infra-up.sh --check
./scripts/infra-up.sh          # ~15-20 min: RDS y entorno tardan
git archive -o deploy.zip HEAD # y súbelo a mano en Beanstalk (Upload and deploy)
./scripts/infra-down.sh        # pide escribir el nombre del entorno
```

- El entorno nace con la **aplicación de ejemplo** de AWS. El hook `.ebextensions` crea las tablas
  cuando despliegas tu zip, y por eso la regla de seguridad de RDS ya está abierta antes.
- `DB_PASSWORD` y `STATIC_TOKEN` se generan una vez y quedan en `.infra-secrets` (fuera de git,
  permisos 600). Ese token es el que se usa en Postman. `infra-down.sh` lo borra.
- Todo se puede ajustar por variable: `DB_CLASS`, `MIN_SIZE`, `MAX_SIZE`, `INSTANCE_TYPES`,
  `PYTHON_VERSION`, `SUBNET_IDS`, `ENV_NAME`...
- Cuesta dinero mientras esté arriba (instancias, balanceador y RDS). Bájala al terminar.
