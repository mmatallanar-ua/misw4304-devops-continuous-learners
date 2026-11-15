# Despliegue

## PostgreSQL local con Docker

```bash
docker compose up -d
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/blacklist STATIC_TOKEN=dev
flask --app application init-db
flask --app application run
docker compose down        # agregar -v para borrar los datos
```

## Despliegue manual en Elastic Beanstalk

1. Empaquetar el código: `git archive -o deploy.zip HEAD` (solo archivos versionados).
2. En el entorno, definir `DATABASE_URL` y `STATIC_TOKEN` en *Configuration → Environment properties*.
3. Subir `deploy.zip` desde *Upload and deploy*.

`.ebextensions/01_init_db.config` corre `init-db` en una instancia (`leader_only`) durante cada
despliegue y crea las tablas en RDS; `create_all` es idempotente. `.ebignore` lista lo que
`eb deploy` no debe subir.

## Entrega continua en AWS Fargate (Entrega 3)

El pipeline `blacklist-ci-pipeline` se dispara con cada push a `main` y tiene tres etapas:

1. **Source**: GitHub, rama `main`.
2. **Build** (CodeBuild, `buildspec.yml`): corre las pruebas unitarias con pytest y, solo si pasan,
   construye la imagen, la publica en ECR con el SHA corto del commit como tag y genera
   `imageDetail.json`.
3. **Deploy** (CodeDeploy, ECS Blue/Green): registra una nueva revisión de la task definition a
   partir de `taskdef.json` (reemplazando `<IMAGE1_NAME>` con la imagen de `imageDetail.json`),
   levanta las tareas nuevas (green) en Fargate, pasa el tráfico del listener 80 del balanceador y,
   tras la espera configurada, apaga las tareas anteriores (blue).

| Archivo | Uso |
|---|---|
| `buildspec.yml` | Pruebas, imagen Docker y artefactos del despliegue |
| `taskdef.json` | Task definition de Fargate: imagen, CPU/memoria, puerto 5000, secretos y logs |
| `appspec.json` | Contenedor y puerto al que el balanceador envía el tráfico |

`DATABASE_URL` y `STATIC_TOKEN` no van en el repositorio: la tarea los lee de SSM Parameter Store
(`/blacklist/*`) mediante el rol de ejecución. `PROXY_X_FOR` vale `1` porque el balanceador envía
el tráfico directo al contenedor (un solo salto de proxy).

`GET /ping` informa la versión desplegada (`version` = SHA corto del commit), lo que permite ver
en Postman cuándo el tráfico pasa a la versión nueva. Para probar contra AWS basta con cambiar
`base_url` (DNS del balanceador) y `token` en el environment de Postman.
