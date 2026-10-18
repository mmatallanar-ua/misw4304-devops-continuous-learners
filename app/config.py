import os


def _database_uri():
    """Resuelve la conexión a la base de datos.

    Prioridad: DATABASE_URL; si no existe, las variables RDS_* que Elastic Beanstalk
    inyecta cuando la base está asociada al entorno.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # SQLAlchemy usa el driver psycopg (v3) solo si el esquema lo indica.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    host = os.environ.get("RDS_HOSTNAME")
    if host:
        return "postgresql+psycopg://{user}:{password}@{host}:{port}/{name}".format(
            user=os.environ["RDS_USERNAME"],
            password=os.environ["RDS_PASSWORD"],
            host=host,
            port=os.environ.get("RDS_PORT", "5432"),
            name=os.environ["RDS_DB_NAME"],
        )
    return "sqlite:///local.db"


class Config:
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STATIC_TOKEN = os.environ.get("STATIC_TOKEN")
