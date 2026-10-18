from flask import current_app
from flask_restful import Resource
from marshmallow import ValidationError, fields, validate
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from .auth import token_required
from .extensions import db
from .models import BlacklistEntry


class BlacklistLookup(Resource):
    email_field = fields.Email(validate=validate.Length(max=255))

    @token_required
    def get(self, email):
        try:
            self.email_field.deserialize(email)
        except ValidationError:
            return {"message": "Email inválido"}, 400

        statement = (
            db.select(BlacklistEntry)
            .where(func.lower(BlacklistEntry.email) == email.lower())
            .order_by(BlacklistEntry.created_at.desc(), BlacklistEntry.id.desc())
            .limit(1)
        )
        try:
            entry = db.session.execute(statement).scalar_one_or_none()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("No se pudo consultar la lista negra")
            return {"message": "Base de datos no disponible"}, 503

        return {
            "blacklisted": entry is not None,
            "blocked_reason": entry.blocked_reason if entry is not None else None,
        }, 200
