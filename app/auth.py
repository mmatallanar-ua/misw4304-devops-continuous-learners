import hmac
from functools import wraps

from flask import current_app, request


def _unauthorized(message):
    return {"message": message}, 401, {"WWW-Authenticate": "Bearer"}


def token_required(view):
    """Exige `Authorization: Bearer <STATIC_TOKEN>`.

    El enunciado permite un token estático para toda la aplicación.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("STATIC_TOKEN")
        if not expected:
            current_app.logger.error("STATIC_TOKEN no está configurado")
            return {"message": "Servidor mal configurado"}, 500

        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return _unauthorized("Falta el token de autorización")
        if not hmac.compare_digest(token.strip(), expected):
            return _unauthorized("Token inválido")
        return view(*args, **kwargs)

    return wrapper
