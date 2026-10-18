from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import BlacklistEntry


AUTH = {"Authorization": "Bearer token-de-prueba"}


def add_entry(email="cliente@example.com", reason="Uso indebido", **kwargs):
    entry = BlacklistEntry(
        email=email,
        blocked_reason=reason,
        app_uuid=kwargs.pop("app_uuid", UUID("11111111-1111-4111-8111-111111111111")),
        ip_address="127.0.0.1",
        **kwargs,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def lookup(client, email="cliente@example.com", headers=None):
    return client.get(
        f"/blacklists/{quote(email, safe='')}",
        headers=AUTH if headers is None else headers,
    )


def test_email_bloqueado_devuelve_booleano_y_motivo(client):
    add_entry()

    response = lookup(client)

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.get_json() == {"blacklisted": True, "blocked_reason": "Uso indebido"}


def test_email_ausente_devuelve_false_y_null(client):
    add_entry(email="otro@example.com")

    response = lookup(client)

    assert response.status_code == 200
    assert response.get_json() == {"blacklisted": False, "blocked_reason": None}


@pytest.mark.parametrize("reason", [None, "", "á" * 255])
def test_conserva_el_motivo_almacenado_incluso_si_es_opcional(client, reason):
    add_entry(reason=reason)

    response = lookup(client)

    assert response.status_code == 200
    assert response.get_json() == {"blacklisted": True, "blocked_reason": reason}


@pytest.mark.parametrize(
    ("stored", "requested"),
    [
        ("Cliente@EXAMPLE.COM", "cliente@example.com"),
        ("cliente@example.com", "CLIENTE@EXAMPLE.COM"),
    ],
)
def test_busqueda_sin_distinguir_mayusculas(client, stored, requested):
    add_entry(email=stored)

    response = lookup(client, requested)

    assert response.status_code == 200
    assert response.get_json()["blacklisted"] is True


def test_duplicados_eligen_fecha_mas_reciente_entre_todas_las_apps(client):
    add_entry(
        email="CLIENTE@EXAMPLE.COM",
        reason="Más reciente",
        created_at=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
        app_uuid=UUID("22222222-2222-4222-8222-222222222222"),
    )
    add_entry(
        reason="Anterior, con id mayor",
        created_at=datetime(2026, 10, 17, 12, tzinfo=timezone.utc),
    )

    response = lookup(client)

    assert response.status_code == 200
    assert response.get_json() == {"blacklisted": True, "blocked_reason": "Más reciente"}


def test_duplicados_desempatan_por_id_mayor(client):
    timestamp = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
    add_entry(reason="Primer registro", created_at=timestamp)
    add_entry(reason="Segundo registro", created_at=timestamp)

    response = lookup(client)

    assert response.status_code == 200
    assert response.get_json()["blocked_reason"] == "Segundo registro"


def test_ultimo_motivo_nulo_no_se_reemplaza_por_uno_anterior(client):
    add_entry(reason="Anterior", created_at=datetime(2026, 10, 17, tzinfo=timezone.utc))
    add_entry(reason=None, created_at=datetime(2026, 10, 18, tzinfo=timezone.utc))

    response = lookup(client)

    assert response.status_code == 200
    assert response.get_json() == {"blacklisted": True, "blocked_reason": None}


@pytest.mark.parametrize("email", ["cliente_prueba@example.com", "cliente%prueba@example.com"])
def test_caracteres_del_email_no_actuan_como_comodines_sql(client, email):
    add_entry(email="clienteXprueba@example.com")

    assert lookup(client, email).get_json() == {"blacklisted": False, "blocked_reason": None}

    add_entry(email=email)
    assert lookup(client, email).get_json()["blacklisted"] is True


def test_preserva_alias_con_signo_mas(client):
    add_entry(email="cliente+alias@example.com")

    assert lookup(client, "cliente+alias@example.com").get_json()["blacklisted"] is True
    assert lookup(client).get_json()["blacklisted"] is False


@pytest.mark.parametrize(
    "email",
    ["sin-arroba", "cliente@@example.com", "@example.com", "cliente@", " cliente@example.com", "a" * 244 + "@example.com"],
)
def test_email_invalido_400_sin_consultar_base(client, monkeypatch, email):
    def unexpected_query(*args, **kwargs):
        pytest.fail("Un email inválido no debe consultar la base de datos")

    monkeypatch.setattr(db.session, "execute", unexpected_query)

    response = lookup(client, email)

    assert response.status_code == 400
    assert response.get_json() == {"message": "Email inválido"}


@pytest.mark.parametrize("domain_tail, expected_status", [(58, 200), (59, 400)])
def test_limite_de_255_caracteres(client, domain_tail, expected_status):
    email = "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * domain_tail + ".com"
    response = lookup(client, email)

    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.get_json() == {"blacklisted": False, "blocked_reason": None}
    else:
        assert response.get_json() == {"message": "Email inválido"}


@pytest.mark.parametrize("authorization", [None, "Bearer incorrecto", "Basic token-de-prueba", "Bearer"])
def test_autenticacion_401_antes_de_consultar_base(client, monkeypatch, authorization):
    def unexpected_query(*args, **kwargs):
        pytest.fail("Una solicitud no autenticada no debe consultar la base de datos")

    monkeypatch.setattr(db.session, "execute", unexpected_query)
    headers = {} if authorization is None else {"Authorization": authorization}

    response = lookup(client, headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "message" in response.get_json()


def test_sin_token_configurado_conserva_error_500(app, client):
    app.config["STATIC_TOKEN"] = None

    response = lookup(client)

    assert response.status_code == 500
    assert response.get_json() == {"message": "Servidor mal configurado"}


def test_base_caida_503_y_sesion_recuperada(client, monkeypatch):
    add_entry()
    rollbacks = []
    original_rollback = db.session.rollback

    def database_down(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("database unavailable"))

    def record_rollback():
        rollbacks.append(True)
        return original_rollback()

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "execute", database_down)
        patch.setattr(db.session, "rollback", record_rollback)
        response = lookup(client)

    assert response.status_code == 503
    assert response.get_json() == {"message": "Base de datos no disponible"}
    assert rollbacks == [True]
    assert lookup(client).get_json()["blacklisted"] is True


def test_consulta_no_modifica_datos_y_no_expone_metadatos(client):
    entry = add_entry()
    before = (entry.email, entry.blocked_reason, entry.app_uuid, entry.ip_address, entry.created_at)
    writes = []

    def record_write(mapper, connection, target):
        writes.append(target)

    for operation in ("after_insert", "after_update", "after_delete"):
        event.listen(BlacklistEntry, operation, record_write)
    try:
        response = lookup(client)
        db.session.expire_all()
        persisted = db.session.get(BlacklistEntry, entry.id)
        after = (persisted.email, persisted.blocked_reason, persisted.app_uuid, persisted.ip_address, persisted.created_at)
        count = db.session.scalar(db.select(db.func.count()).select_from(BlacklistEntry))
    finally:
        for operation in ("after_insert", "after_update", "after_delete"):
            event.remove(BlacklistEntry, operation, record_write)

    assert response.status_code == 200
    assert set(response.get_json()) == {"blacklisted", "blocked_reason"}
    assert count == 1
    assert before == after
    assert writes == []
