import click
from flask import Flask
from flask_restful import Api
from werkzeug.middleware.proxy_fix import ProxyFix

from .blacklists import BlacklistCreate, BlacklistLookup
from .config import Config
from .extensions import db, ma
from .health import Health
from .ping import Ping


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    # Beanstalk pone nginx/ELB delante de la app: sin esto, request.remote_addr
    # sería la IP interna del proxy y no la del cliente real. PROXY_X_FOR debe ser 2 en un
    # entorno con balanceador de carga (ALB + nginx = dos saltos) y 1 en una instancia única.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["PROXY_X_FOR"])

    db.init_app(app)
    ma.init_app(app)

    api = Api(app)
    api.add_resource(Health, "/health")
    api.add_resource(Ping, "/ping")
    api.add_resource(BlacklistCreate, "/blacklists")
    api.add_resource(BlacklistLookup, "/blacklists/<string:email>")

    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas si no existen."""
        from . import models  # noqa: F401  (registra los modelos)

        db.create_all()
        click.echo("Tablas creadas")

    return app
