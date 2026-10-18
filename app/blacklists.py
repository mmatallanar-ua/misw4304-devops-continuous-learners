from flask import current_app, request
from flask_restful import Resource
from marshmallow import ValidationError, fields, validate
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from .auth import token_required
from .extensions import db
from .models import BlacklistEntry


class BlacklistCreate(Resource):
    email_field = fields.Email(validate=validate.Length(max=255))
    app_uuid_field = fields.UUID()
    reason_field = fields.String(validate=validate.Length(max=255))

    @token_required
    def post(self):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return {"message": "Cuerpo JSON inválido"}, 400

        errors = {}

        try:
            email = self.email_field.deserialize(payload.get("email"))
        except ValidationError as err:
            errors["email"] = err.messages
            email = None

        try:
            app_uuid = self.app_uuid_field.deserialize(payload.get("app_uuid"))
        except ValidationError as err:
            errors["app_uuid"] = err.messages
            app_uuid = None

        blocked_reason = payload.get("blocked_reason")
        if blocked_reason is not None:
            try:
                blocked_reason = self.reason_field.deserialize(blocked_reason)
            except ValidationError as err:
                errors["blocked_reason"] = err.messages
            else:
                # Normaliza "" a None para que ausente, null y cadena vacía se guarden y se
                # consulten siempre de la misma forma (ver GET /blacklists/<email>).
                if blocked_reason == "":
                    blocked_reason = None

        if errors:
            return {"message": "Datos inválidos", "errors": errors}, 400

        entry = BlacklistEntry(
            email=email,
            app_uuid=app_uuid,
            blocked_reason=blocked_reason,
            ip_address=request.remote_addr or "0.0.0.0",
        )
        db.session.add(entry)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("No se pudo agregar el email a la lista negra")
            return {"message": "Base de datos no disponible"}, 503

        return {"message": "Email agregado a la lista negra global"}, 201


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
