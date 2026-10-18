# misw4304-devops-continuous-learners

Microservicio Flask de **lista negra global de emails** (Entrega 1 · Despliegue manual en AWS
Elastic Beanstalk). Documentación de los endpoints: [`docs/blacklists-post.md`](docs/blacklists-post.md)
y [`docs/blacklists-get.md`](docs/blacklists-get.md).

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

## Agregar un email a la lista negra

`POST /blacklists` requiere `Authorization: Bearer <STATIC_TOKEN>` y un cuerpo JSON con `email`,
`app_uuid` (UUID) y, opcionalmente, `blocked_reason` (máx. 255 caracteres). Guarda la IP real del
cliente y la fecha/hora de la solicitud. Ver el [contrato completo](docs/blacklists-post.md).

## Consultar la lista negra

`GET /blacklists/<string:email>` requiere `Authorization: Bearer <STATIC_TOKEN>` y devuelve
`blacklisted` (booleano) y `blocked_reason` (texto o `null`). La consulta ignora mayúsculas y,
si hay duplicados, usa el registro más reciente por fecha y luego por id.

Ver el [contrato y los escenarios de prueba](docs/blacklists-get.md) y la
[colección de Postman](docs/postman/blacklists-get.postman_collection.json).

## Variables de entorno

| Variable | Uso |
|---|---|
| `STATIC_TOKEN` | Bearer token estático que exigen los endpoints protegidos |
| `DATABASE_URL` | Conexión a PostgreSQL |
| `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD` | Alternativa a `DATABASE_URL`; las inyecta Beanstalk con RDS asociada |

## Despliegue

`application.py` expone el objeto `application` y el `Procfile` arranca con gunicorn, que es lo
que espera Elastic Beanstalk (plataforma Python).
