from app.auth import token_required


def test_health_no_requiere_token(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def _register_protected(app):
    @app.get("/_protegido")
    @token_required
    def protegido():
        return {"ok": True}


def test_sin_token_401(app, client):
    _register_protected(app)
    resp = client.get("/_protegido")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_token_invalido_401(app, client):
    _register_protected(app)
    resp = client.get("/_protegido", headers={"Authorization": "Bearer otro"})
    assert resp.status_code == 401


def test_token_valido_200(app, client):
    _register_protected(app)
    resp = client.get("/_protegido", headers={"Authorization": "Bearer token-de-prueba"})
    assert resp.status_code == 200
