from flask_restful import Resource
from sqlalchemy import text

from .extensions import db


class Ping(Resource):
    """Prueba manual de extremo a extremo: app arriba y base de datos alcanzable.

    A diferencia de /health (que usan los health checks y no toca la base), este endpoint
    ejecuta `SELECT 1`, así que sirve para validar la conexión con RDS desde Postman.
    """

    def get(self):
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            return {"message": "pong", "database": "error"}, 503
        return {"message": "pong", "database": "ok"}, 200
