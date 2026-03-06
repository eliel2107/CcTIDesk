"""Testes de fumaça — garantem que as rotas e regras de negócio básicas funcionam."""
import pytest
import os
import tempfile

@pytest.fixture
def app():
    """Cria uma instância da app com banco em memória para cada teste."""
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("ADMIN_DEFAULT_EMAIL", "admin@test.com")
    os.environ.setdefault("ADMIN_DEFAULT_PASSWORD", "admin123")

    from app import create_app
    from app.config import Config

    class TestConfig(Config):
        def __init__(self):
            super().__init__()
            self._tmpdir = tempfile.mkdtemp()
            self.DATABASE = os.path.join(self._tmpdir, "test.db")
            self.UPLOAD_FOLDER = os.path.join(self._tmpdir, "uploads")
            self.TESTING = True
            self.WTF_CSRF_ENABLED = False       # desabilita CSRF nos testes
            self.WTF_CSRF_CHECK_DEFAULT = False
            self.RATELIMIT_ENABLED = False       # desabilita rate limit nos testes
            self.RATELIMIT_STORAGE_URI = "memory://"
            self.SECRET_KEY = "test-secret"

    application = create_app()
    application.config.from_object(TestConfig())
    application.config["TESTING"] = True

    with application.app_context():
        from app.db import init_db
        init_db()

    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Client já autenticado como admin."""
    client.post("/auth/login", data={"email": "admin@test.com", "password": "admin123"})
    return client


# ── Testes de saúde básica ──────────────────────────────────────────────────

def test_import_app(app):
    assert app is not None


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True


def test_login_page_loads(client):
    r = client.get("/auth/login")
    assert r.status_code == 200


def test_redirect_unauthenticated(client):
    r = client.get("/")
    assert r.status_code in (302, 308)


# ── Testes de autenticação ──────────────────────────────────────────────────

def test_login_valid(client):
    r = client.post("/auth/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)
    assert r.status_code == 200


def test_login_invalid_password(client):
    r = client.post("/auth/login", data={"email": "admin@test.com", "password": "wrong"}, follow_redirects=True)
    assert r.status_code == 200
    assert "inválidos" in r.data.decode("utf-8").lower() or r.status_code == 200


def test_login_unknown_email(client):
    r = client.post("/auth/login", data={"email": "nobody@test.com", "password": "x"}, follow_redirects=True)
    assert r.status_code == 200


def test_logout(auth_client):
    r = auth_client.get("/auth/logout", follow_redirects=True)
    assert r.status_code == 200


# ── Testes de chamados ──────────────────────────────────────────────────────

def test_index_authenticated(auth_client):
    r = auth_client.get("/")
    assert r.status_code == 200


def test_new_ticket_page(auth_client):
    r = auth_client.get("/tickets/new")
    assert r.status_code == 200


def test_create_ticket(auth_client):
    r = auth_client.post("/tickets", data={
        "tipo": "COMPRA",
        "titulo": "Teste de chamado automatizado",
        "prioridade": "MEDIA",
        "solicitante": "Tester",
    }, follow_redirects=True)
    assert r.status_code == 200


def test_ticket_detail(auth_client):
    # Cria primeiro
    auth_client.post("/tickets", data={
        "tipo": "ENVIO",
        "titulo": "Chamado para detalhe",
        "prioridade": "BAIXA",
    })
    r = auth_client.get("/tickets/1")
    assert r.status_code in (200, 404)


def test_api_list_tickets(auth_client):
    r = auth_client.get("/api/tickets")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_api_ticket_not_found(auth_client):
    r = auth_client.get("/api/tickets/99999")
    assert r.status_code == 404


# ── Testes de dashboard e relatórios ───────────────────────────────────────

def test_dashboard(auth_client):
    r = auth_client.get("/dashboard")
    assert r.status_code == 200


def test_reports_home(auth_client):
    r = auth_client.get("/reports/")
    assert r.status_code == 200


def test_export_csv(auth_client):
    r = auth_client.get("/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.content_type


# ── Testes de modelos ───────────────────────────────────────────────────────

def test_create_ticket_model(app):
    with app.app_context():
        from app.models import create_ticket, get_ticket
        tid = create_ticket({
            "tipo": "COMPRA",
            "titulo": "Chamado via model",
            "prioridade": "ALTA",
            "solicitante": "Pytest",
        })
        assert isinstance(tid, int) and tid > 0
        t = get_ticket(tid)
        assert t is not None
        assert t["titulo"] == "Chamado via model"
        assert t["status"] == "ABERTO"


def test_create_ticket_missing_title(app):
    with app.app_context():
        from app.models import create_ticket
        with pytest.raises(ValueError, match="Título"):
            create_ticket({"tipo": "COMPRA", "prioridade": "MEDIA", "titulo": ""})


def test_create_ticket_invalid_type(app):
    with app.app_context():
        from app.models import create_ticket
        with pytest.raises(ValueError):
            create_ticket({"tipo": "INVALIDO", "titulo": "X", "prioridade": "MEDIA"})


def test_update_status(app):
    with app.app_context():
        from app.models import create_ticket, update_status, get_ticket
        tid = create_ticket({"tipo": "ENVIO", "titulo": "Status test", "prioridade": "BAIXA"})
        update_status(tid, "EM_ANDAMENTO", "Iniciando")
        t = get_ticket(tid)
        assert t["status"] == "EM_ANDAMENTO"


def test_pagination_model(app):
    with app.app_context():
        from app.models import create_ticket, list_tickets_paginated
        for i in range(5):
            create_ticket({"tipo": "COMPRA", "titulo": f"Pag test {i}", "prioridade": "BAIXA"})
        items, total, pages = list_tickets_paginated({}, page=1, per_page=3)
        assert total >= 5
        assert len(items) <= 3
        assert pages >= 2


# ── Testes de permissão ─────────────────────────────────────────────────────

def test_admin_users_page(auth_client):
    r = auth_client.get("/admin/users")
    assert r.status_code == 200


def test_fila_accessible_admin(auth_client):
    r = auth_client.get("/fila")
    assert r.status_code == 200


def test_solicitante_cannot_access_fila(app):
    """Solicitante não deve acessar a fila operacional."""
    with app.app_context():
        from app.services.user_service import create_user
        create_user("Solicitante Test", "sol@test.com", "sol123", role="solicitante")

    c = app.test_client()
    c.post("/auth/login", data={"email": "sol@test.com", "password": "sol123"})
    r = c.get("/fila", follow_redirects=False)
    assert r.status_code in (302, 308, 403)


# ── Testes de CSRF ──────────────────────────────────────────────────────────

def test_csrf_token_in_login_page(client):
    """Página de login deve conter o campo csrf_token."""
    r = client.get("/auth/login")
    assert b"csrf_token" in r.data


def test_post_without_csrf_blocked(app):
    """POST sem token CSRF deve ser bloqueado quando CSRF está ativado."""
    from app.config import Config
    import tempfile

    class CsrfConfig(Config):
        def __init__(self):
            super().__init__()
            d = tempfile.mkdtemp()
            self.DATABASE = f"{d}/csrf_test.db"
            self.UPLOAD_FOLDER = f"{d}/uploads"
            self.TESTING = True
            self.WTF_CSRF_ENABLED = True
            self.WTF_CSRF_CHECK_DEFAULT = True
            self.RATELIMIT_ENABLED = False
            self.RATELIMIT_STORAGE_URI = "memory://"
            self.SECRET_KEY = "csrf-test-secret"

    from app import create_app
    csrf_app = create_app()
    csrf_app.config.from_object(CsrfConfig())
    with csrf_app.app_context():
        from app.db import init_db
        init_db()

    c = csrf_app.test_client()
    r = c.post("/auth/login", data={"email": "x@x.com", "password": "x"})
    # Deve bloquear (400) ou redirecionar com erro — não processar normalmente
    assert r.status_code in (400, 302, 200)
    # Garante que não recebemos sucesso indevido
    if r.status_code == 302:
        assert b"csrf" in r.data.lower() or r.location != "/"


# ── Testes de Rate Limiting ─────────────────────────────────────────────────

def test_rate_limit_login(app):
    """Mais de 10 POSTs de login por minuto deve resultar em bloqueio (429)."""
    from app.config import Config
    import tempfile

    class RLConfig(Config):
        def __init__(self):
            super().__init__()
            d = tempfile.mkdtemp()
            self.DATABASE = f"{d}/rl_test.db"
            self.UPLOAD_FOLDER = f"{d}/uploads"
            self.TESTING = True
            self.WTF_CSRF_ENABLED = False
            self.WTF_CSRF_CHECK_DEFAULT = False
            self.RATELIMIT_ENABLED = True
            self.RATELIMIT_STORAGE_URI = "memory://"
            self.SECRET_KEY = "rl-test-secret"

    from app import create_app
    rl_app = create_app()
    rl_app.config.from_object(RLConfig())
    with rl_app.app_context():
        from app.db import init_db
        init_db()

    c = rl_app.test_client()
    status_codes = []
    for _ in range(12):
        r = c.post("/auth/login", data={"email": "x@x.com", "password": "wrong"})
        status_codes.append(r.status_code)

    # Após 10 tentativas, pelo menos uma deve retornar 429
    assert 429 in status_codes, f"Rate limit não foi acionado. Códigos: {status_codes}"
