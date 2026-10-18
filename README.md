# misw4304-devops-continuous-learners

Microservicio Flask de **lista negra global de emails** (Entrega 1 · Despliegue manual en AWS
Elastic Beanstalk). Historias de usuario en [`docs/historias-entrega1.md`](docs/historias-entrega1.md).

## Correr en local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # y completar STATIC_TOKEN / DATABASE_URL
set -a; source .env; set +a
flask --app application init-db   # crea las tablas
flask --app application run
curl localhost:5000/health
```

Sin `DATABASE_URL` ni `RDS_*` usa SQLite local (`local.db`), solo para desarrollo.

## Pruebas

```bash
python -m pytest
```

## Variables de entorno

| Variable | Uso |
|---|---|
| `STATIC_TOKEN` | Bearer token estático que exigen los endpoints protegidos |
| `DATABASE_URL` | Conexión a PostgreSQL |
| `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD` | Alternativa a `DATABASE_URL`; las inyecta Beanstalk con RDS asociada |

## Despliegue

`application.py` expone el objeto `application` y el `Procfile` arranca con gunicorn, que es lo
que espera Elastic Beanstalk (plataforma Python).
