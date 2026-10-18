import socket
from pathlib import Path

from flask_restful import Resource
from sqlalchemy import text

from .extensions import db

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def _version():
    """Etiqueta de la versión desplegada, leída del archivo VERSION en la raíz del paquete.
    Sin ese archivo (local, tests) vale "dev"."""
    try:
        return _VERSION_FILE.read_text().strip() or "dev"
    except OSError:
        return "dev"


class Ping(Resource):
    """Prueba manual de extremo a extremo: app arriba y base de datos alcanzable.

    A diferencia de /health (que usan los health checks y no toca la base), este endpoint
    ejecuta `SELECT 1`, así que sirve para validar la conexión con RDS desde Postman.
    También informa la versión y la instancia que atendió la solicitud, para distinguir qué
    instancias ya recibieron un despliegue.
    """

    def get(self):
        info = {"version": _version(), "instance": socket.gethostname()}
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            return {"message": "pong", "database": "error", **info}, 503
        return {"message": "pong", "database": "ok", **info}, 200
