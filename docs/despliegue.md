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
