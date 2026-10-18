import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import BlacklistEntry


AUTH = {"Authorization": "Bearer token-de-prueba"}
VALID_UUID = "11111111-1111-4111-8111-111111111111"


def create(client, payload, headers=None, **kwargs):
    return client.post(
        "/blacklists",
        data=json.dumps(payload),
        content_type="application/json",
        headers=AUTH if headers is None else headers,
        **kwargs,
    )


def count_entries():
    return db.session.execute(db.select(db.func.count()).select_from(BlacklistEntry)).scalar()


def test_crea_registro_y_responde_201(client):
    response = create(
        client,
        {"email": "cliente@example.com", "app_uuid": VALID_UUID, "blocked_reason": "Fraude"},
    )

    assert response.status_code == 201
    assert response.get_json() == {"message": "Email agregado a la lista negra global"}
    entry = db.session.execute(db.select(BlacklistEntry)).scalar_one()
    assert entry.email == "cliente@example.com"
    assert entry.app_uuid == UUID(VALID_UUID)
    assert entry.blocked_reason == "Fraude"


def test_blocked_reason_es_opcional(client):
    response = create(client, {"email": "cliente@example.com", "app_uuid": VALID_UUID})

    assert response.status_code == 201
    entry = db.session.execute(db.select(BlacklistEntry)).scalar_one()
    assert entry.blocked_reason is None


def test_guarda_la_ip_real_detras_del_proxy(client):
    response = client.post(
        "/blacklists",
        data=json.dumps({"email": "cliente@example.com", "app_uuid": VALID_UUID}),
        content_type="application/json",
        headers={**AUTH, "X-Forwarded-For": "203.0.113.5"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.5"},
    )

    assert response.status_code == 201
    entry = db.session.execute(db.select(BlacklistEntry)).scalar_one()
    assert entry.ip_address == "203.0.113.5"


def test_guarda_fecha_de_la_solicitud(client):
    before = datetime.now(timezone.utc)
    create(client, {"email": "cliente@example.com", "app_uuid": VALID_UUID})
    after = datetime.now(timezone.utc)

    entry = db.session.execute(db.select(BlacklistEntry)).scalar_one()
    stored = entry.created_at
    if stored.tzinfo is None:
        # SQLite no conserva el offset de un DateTime(timezone=True); se asume UTC,
        # que es lo que guarda _utcnow() en app/models.py.
        stored = stored.replace(tzinfo=timezone.utc)
    assert before <= stored <= after


@pytest.mark.parametrize(
    "payload",
    [
        {"app_uuid": VALID_UUID},
        {"email": "cliente@example.com"},
        {"email": "sin-arroba", "app_uuid": VALID_UUID},
        {"email": "cliente@example.com", "app_uuid": "no-es-uuid"},
        {"email": "cliente@example.com", "app_uuid": VALID_UUID, "blocked_reason": "a" * 256},
    ],
)
def test_datos_invalidos_devuelven_400_sin_crear_registro(client, payload):
    response = create(client, payload)

    assert response.status_code == 400
    assert count_entries() == 0


def test_cuerpo_no_json_devuelve_400(client):
    response = client.post("/blacklists", data="no-es-json", content_type="text/plain", headers=AUTH)

    assert response.status_code == 400
    assert count_entries() == 0


def test_permite_duplicar_email_entre_apps(client):
    create(client, {"email": "cliente@example.com", "app_uuid": VALID_UUID, "blocked_reason": "Primero"})
    other_uuid = "22222222-2222-4222-8222-222222222222"
    response = create(
        client,
        {"email": "cliente@example.com", "app_uuid": other_uuid, "blocked_reason": "Segundo"},
    )

    assert response.status_code == 201
    assert count_entries() == 2


@pytest.mark.parametrize("authorization", [None, "Bearer incorrecto", "Basic token-de-prueba", "Bearer"])
def test_autenticacion_401_antes_de_crear_registro(client, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}

    response = create(client, {"email": "cliente@example.com", "app_uuid": VALID_UUID}, headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert count_entries() == 0


def test_sin_token_configurado_conserva_error_500(app, client):
    app.config["STATIC_TOKEN"] = None

    response = create(client, {"email": "cliente@example.com", "app_uuid": VALID_UUID})

    assert response.status_code == 500
    assert response.get_json() == {"message": "Servidor mal configurado"}


def test_base_caida_503_y_no_deja_registro_a_medias(client, monkeypatch):
    def database_down(*args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db.session, "commit", database_down)

    response = create(client, {"email": "cliente@example.com", "app_uuid": VALID_UUID})

    assert response.status_code == 503
    assert response.get_json() == {"message": "Base de datos no disponible"}
    assert count_entries() == 0
