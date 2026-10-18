import click
from flask import Flask
from flask_restful import Api

from .config import Config
from .extensions import db, ma
from .health import Health


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    ma.init_app(app)

    api = Api(app)
    api.add_resource(Health, "/health")

    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas si no existen."""
        from . import models  # noqa: F401  (registra los modelos)

        db.create_all()
        click.echo("Tablas creadas")

    return app
