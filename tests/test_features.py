"""
Testes de integração para as novas features:
- WAL mode no SQLite
- Histórico de edição campo a campo
- Atribuição automática ao criar chamado
- Base de Conhecimento (KB)
- Portal externo via token
- Chamados recorrentes (model)
- Devolução / reenvio
- Busca global API
- Scheduler backup (mock)
- Digest diário (mock)
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


# ── Fixture compartilhada ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("SECRET_KEY", "test-secret-features")
    os.environ.setdefault("ADMIN_DEFAULT_EMAIL", "admin@test.com")
    os.environ.setdefault("ADMIN_DEFAULT_PASSWORD", "admin123")
    os.environ["FLASK_ENV"] = "development"  # evita warnings de produção

    from app import create_app
    from app.config import Config

    class TestConfig(Config):
        def __init__(self):
            super().__init__()
            self._tmpdir = tempfile.mkdtemp()
            self.DATABASE = os.path.join(self._tmpdir, "test_features.db")
            self.UPLOAD_FOLDER = os.path.join(self._tmpdir, "uploads")
            self.BACKUP_DIR = os.path.join(self._tmpdir, "backups")
            self.TESTING = True
            self.WTF_CSRF_ENABLED = False
            self.WTF_CSRF_CHECK_DEFAULT = False
            self.RATELIMIT_ENABLED = False
            self.RATELIMIT_STORAGE_URI = "memory://"
            self.SECRET_KEY = "test-secret-features"
            self.SMTP_HOST = ""  # desabilita e-mail

    application = create_app()
    application.config.from_object(TestConfig())
    with application.app_context():
        from app.db import init_db
        init_db()
    yield application


@pytest.fixture
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    client.post("/auth/login", data={"email": "admin@test.com", "password": "admin123"})
    return client


# ── 1. WAL mode ──────────────────────────────────────────────────────────────

def test_wal_mode_enabled(ctx):
    from app.db import get_db
    mode = get_db().execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal", f"Esperado WAL, obtido: {mode}"


def test_foreign_keys_enabled(ctx):
    from app.db import get_db
    fk = get_db().execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1, "Foreign keys devem estar ativadas"


# ── 2. Histórico de edição campo a campo ─────────────────────────────────────

def test_update_fields_diff_logged(ctx):
    from app.models import create_ticket, update_fields, get_logs
    tid = create_ticket({"tipo": "COMPRA", "titulo": "Diff test", "prioridade": "MEDIA",
                          "solicitante": "Pytest"})
    update_fields(tid, {"responsavel": "Novo Responsável", "prioridade": "ALTA"})
    logs = get_logs(tid)
    edit_logs = [l for l in logs if l["evento"] == "EDITADO"]
    assert len(edit_logs) >= 1
    detalhe = edit_logs[-1]["detalhe"]
    assert "Responsável" in detalhe
    assert "Novo Responsável" in detalhe


def test_update_fields_no_change_logged(ctx):
    from app.models import create_ticket, update_fields, get_logs
    tid = create_ticket({"tipo": "ENVIO", "titulo": "No diff test", "prioridade": "BAIXA"})
    # Salvar sem alterar nada
    update_fields(tid, {})
    logs = get_logs(tid)
    edit_logs = [l for l in logs if l["evento"] == "EDITADO"]
    # Deve registrar, mas com mensagem de sem alterações
    assert any("Sem alterações" in (l["detalhe"] or "") for l in edit_logs)


# ── 3. Atribuição automática ──────────────────────────────────────────────────

def test_queue_first_with_category(app):
    """Chamado criado com categoria deve entrar na fila primeiro e só depois poder ser autoatribuído por timeout."""
    with app.app_context():
        from app.db import get_db
        from app.models import create_ticket, get_ticket, auto_assign_overdue_tickets, get_logs
        from app.services.user_service import create_user

        db = get_db()

        op_id = create_user("Operador Auto", "op_auto@test.com", "senha123", role="operador")
        db.execute(
            "INSERT INTO categories (nome, descricao, cor, ativo, criado_em) VALUES (?,?,?,1,datetime('now'))",
            ("Cat Auto", "", "#6366f1")
        )
        db.commit()
        cat_id = db.execute("SELECT id FROM categories WHERE nome='Cat Auto'").fetchone()["id"]
        db.execute("INSERT INTO user_categories (user_id, category_id) VALUES (?,?)", (op_id, cat_id))
        db.commit()

        tid = create_ticket({
            "tipo": "COMPRA", "titulo": "Queue first test",
            "prioridade": "MEDIA", "categoria_id": str(cat_id),
        })
        t = get_ticket(tid)
        assert t["assigned_user_id"] is None
        assert t["status"] == "ABERTO"

        db.execute("UPDATE tickets SET criado_em='2000-01-01 00:00:00' WHERE id=?", (tid,))
        db.commit()
        processed = auto_assign_overdue_tickets(15)
        t = get_ticket(tid)
        assert processed >= 1
        assert t["assigned_user_id"] == op_id
        assert t["status"] == "EM_ANDAMENTO"
        assert any(l["evento"] == "ATRIBUIDO_TIMEOUT" for l in get_logs(tid))


# ── 4. Base de Conhecimento ───────────────────────────────────────────────────

def test_kb_create_and_list(auth):
    r = auth.post("/kb/novo", data={
        "titulo": "Como resetar a VPN",
        "conteudo": "Passos para resetar a VPN corporativa...",
        "tags": "vpn, rede",
        "publico": "1",
    }, follow_redirects=True)
    assert r.status_code == 200

    r = auth.get("/kb/")
    assert r.status_code == 200
    assert b"Como resetar a VPN" in r.data


def test_kb_article_view_increments_views(app):
    with app.app_context():
        from app.db import get_db
        db = get_db()
        db.execute(
            """INSERT INTO kb_articles (titulo, conteudo, publico, visualizacoes, criado_em, atualizado_em)
               VALUES ('Artigo Views Test', 'Conteudo', 1, 0, datetime('now'), datetime('now'))"""
        )
        db.commit()
        art_id = db.execute("SELECT id FROM kb_articles WHERE titulo='Artigo Views Test'").fetchone()["id"]

    c = app.test_client()
    c.post("/auth/login", data={"email": "admin@test.com", "password": "admin123"})
    c.get(f"/kb/{art_id}")

    with app.app_context():
        from app.db import get_db
        views = get_db().execute("SELECT visualizacoes FROM kb_articles WHERE id=?", (art_id,)).fetchone()[0]
        assert views == 1


def test_kb_suggest_api(auth):
    r = auth.get("/kb/api/sugestoes?q=vpn")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)


def test_kb_internal_not_visible_to_solicitante(app):
    with app.app_context():
        from app.db import get_db
        from app.services.user_service import create_user
        db = get_db()
        create_user("Sol KB", "sol_kb@test.com", "sol123", role="solicitante")
        db.execute(
            """INSERT INTO kb_articles (titulo, conteudo, publico, visualizacoes, criado_em, atualizado_em)
               VALUES ('Artigo Interno', 'Segredo', 0, 0, datetime('now'), datetime('now'))"""
        )
        db.commit()
        art_id = db.execute("SELECT id FROM kb_articles WHERE titulo='Artigo Interno'").fetchone()["id"]

    c = app.test_client()
    c.post("/auth/login", data={"email": "sol_kb@test.com", "password": "sol123"})
    r = c.get(f"/kb/{art_id}", follow_redirects=True)
    assert b"Artigo Interno" not in r.data or b"n\xc3\xa3o dispon\xc3\xadvel" in r.data


# ── 5. Portal externo via token ───────────────────────────────────────────────

def test_portal_token_create_and_view(app):
    with app.app_context():
        from app.models import create_ticket
        from app.portal import create_portal_token
        tid = create_ticket({"tipo": "COMPRA", "titulo": "Portal test",
                              "prioridade": "MEDIA", "solicitante": "Externo"})
        token = create_portal_token(tid, email="externo@test.com")
        assert len(token) > 10

    c = app.test_client()
    r = c.get(f"/portal/{token}")
    assert r.status_code == 200
    assert b"Portal test" in r.data


def test_portal_invalid_token_returns_404(app):
    c = app.test_client()
    r = c.get("/portal/token-invalido-xyz123")
    assert r.status_code == 404


def test_portal_token_generation_route(auth, app):
    with app.app_context():
        from app.models import create_ticket
        tid = create_ticket({"tipo": "ENVIO", "titulo": "Token gen test", "prioridade": "BAIXA"})

    r = auth.post(f"/tickets/{tid}/gerar-token", data={"email": ""}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Link gerado" in r.data


# ── 6. Devolução e reenvio ────────────────────────────────────────────────────

def test_devolver_ticket(app):
    with app.app_context():
        from app.models import create_ticket, devolver_ao_solicitante, get_ticket
        tid = create_ticket({"tipo": "COMPRA", "titulo": "Devolver test",
                              "prioridade": "ALTA", "solicitante": "User"})
        devolver_ao_solicitante(tid, "Operador", "Faltou número de série")
        t = get_ticket(tid)
        assert t["status"] == "AGUARDANDO_INFO"
        assert "número de série" in (t["motivo_devolucao"] or "")


def test_reenviar_ticket_goes_to_assigned(app):
    with app.app_context():
        from app.models import create_ticket, update_fields, devolver_ao_solicitante, reenviar_pelo_solicitante, get_ticket
        from app.services.user_service import create_user
        from app.db import get_db

        op_id = create_user("Op Reenv", "op_reenv@test.com", "s123", role="operador")
        tid = create_ticket({"tipo": "COMPRA", "titulo": "Reenvio test",
                              "prioridade": "MEDIA", "solicitante": "User"})
        # Atribuir manualmente
        db = get_db()
        db.execute("UPDATE tickets SET assigned_user_id=?, responsavel='Op Reenv', status='EM_ANDAMENTO' WHERE id=?",
                   (op_id, tid))
        db.commit()

        devolver_ao_solicitante(tid, "Op Reenv", "Preciso de mais detalhes")
        reenviar_pelo_solicitante(tid, "Solicitante", "Aqui estão os detalhes")

        t = get_ticket(tid)
        # Tinha responsável → deve voltar para EM_ANDAMENTO, não ABERTO
        assert t["status"] == "EM_ANDAMENTO"


def test_reenviar_ticket_without_assigned_goes_to_aberto(app):
    with app.app_context():
        from app.models import create_ticket, devolver_ao_solicitante, reenviar_pelo_solicitante, get_ticket
        from app.db import get_db

        tid = create_ticket({"tipo": "ENVIO", "titulo": "Reenvio sem resp",
                              "prioridade": "BAIXA", "solicitante": "User"})
        # Garantir sem responsável
        db = get_db()
        db.execute("UPDATE tickets SET assigned_user_id=NULL, status='ABERTO' WHERE id=?", (tid,))
        db.commit()

        devolver_ao_solicitante(tid, "Operador X", "Mais info necessária")
        reenviar_pelo_solicitante(tid, "Solicitante", "Enviando info")
        t = get_ticket(tid)
        assert t["status"] == "ABERTO"


# ── 7. Busca global API ───────────────────────────────────────────────────────

def test_global_search_returns_tickets(auth, app):
    with app.app_context():
        from app.models import create_ticket
        create_ticket({"tipo": "COMPRA", "titulo": "Chamado busca unico xyz987",
                        "prioridade": "MEDIA", "solicitante": "Tester"})

    r = auth.get("/api/search?q=xyz987")
    assert r.status_code == 200
    data = r.get_json()
    assert any(item["type"] == "ticket" for item in data["results"])


def test_global_search_short_query_empty(auth):
    r = auth.get("/api/search?q=a")
    assert r.status_code == 200
    data = r.get_json()
    assert data["results"] == []


def test_global_search_requires_auth(client):
    r = client.get("/api/search?q=teste")
    assert r.status_code in (302, 308, 401, 403)


# ── 8. Chamados recorrentes ───────────────────────────────────────────────────

def test_recurring_create_and_list(auth):
    r = auth.post("/recorrentes/novo", data={
        "titulo": "Backup mensal de servidores",
        "frequencia": "mensal",
        "dia_execucao": "1",
        "hora_execucao": "08:00",
        "prioridade": "ALTA",
        "descricao": "Verificar backup de todos os servidores",
    }, follow_redirects=True)
    assert r.status_code == 200

    r = auth.get("/recorrentes")
    assert r.status_code == 200
    assert b"Backup mensal" in r.data


def test_recurring_toggle(auth, app):
    with app.app_context():
        from app.db import get_db
        from app.models import _now
        db = get_db()
        db.execute(
            "INSERT INTO recurring_tickets (titulo, frequencia, dia_execucao, hora_execucao, ativo, criado_em) VALUES (?,?,?,?,1,?)",
            ("Toggle test", "mensal", 1, "09:00", _now())
        )
        db.commit()
        rid = db.execute("SELECT id FROM recurring_tickets WHERE titulo='Toggle test'").fetchone()["id"]

    r = auth.post(f"/recorrentes/{rid}/toggle", follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from app.db import get_db
        row = get_db().execute("SELECT ativo FROM recurring_tickets WHERE id=?", (rid,)).fetchone()
        assert row["ativo"] == 0  # foi desativado


# ── 9. Scheduler — backup ─────────────────────────────────────────────────────

def test_backup_creates_file(app):
    with app.app_context():
        from app.scheduler import run_backup
        backup_dir = app.config["BACKUP_DIR"]
        os.makedirs(backup_dir, exist_ok=True)

        run_backup(app)

        backups = [f for f in os.listdir(backup_dir) if f.endswith(".db")]
        assert len(backups) >= 1, "Backup não criou nenhum arquivo .db"


def test_backup_cleans_old_files(app):
    """Arquivos mais antigos que keep_days devem ser removidos."""
    import time
    with app.app_context():
        backup_dir = app.config["BACKUP_DIR"]
        os.makedirs(backup_dir, exist_ok=True)

        # Criar arquivo "antigo" (modtime no passado)
        old_file = os.path.join(backup_dir, "chamados_19990101_000000.db")
        open(old_file, "w").close()
        old_time = 0  # epoch — definitivamente mais velho que 30 dias
        os.utime(old_file, (old_time, old_time))

        from app.scheduler import run_backup
        run_backup(app)

        assert not os.path.exists(old_file), "Backup antigo não foi removido"


# ── 10. Scheduler — digest diário (mock SMTP) ─────────────────────────────────

def test_daily_digest_runs_without_smtp(app):
    """Digest não deve falhar mesmo sem SMTP configurado (apenas silencia)."""
    with app.app_context():
        from app.scheduler import run_daily_digest
        # Não deve levantar exceção
        run_daily_digest(app)


def test_daily_digest_sends_when_smtp_configured(app):
    """Com SMTP configurado, deve chamar notify_async."""
    with app.app_context():
        app.config["SMTP_HOST"] = "smtp.fake.com"
        app.config["ALERT_TO_EMAILS"] = ["admin@test.com"]
        try:
            with patch("app.scheduler.notify_async") as mock_notify:
                from app.scheduler import run_daily_digest
                run_daily_digest(app)
                mock_notify.assert_called_once()
                call_args = mock_notify.call_args
                assert "Resumo diário" in call_args[0][2]  # subject
        finally:
            app.config["SMTP_HOST"] = ""
            app.config["ALERT_TO_EMAILS"] = []


# ── 11. Validação de config em produção ───────────────────────────────────────

def test_config_warns_insecure_secret_in_production():
    import warnings
    os.environ["FLASK_ENV"] = "production"
    os.environ["SECRET_KEY"] = "dev-secret-change-me"
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from app.config import Config
            Config()
            assert any("SECRET_KEY" in str(warning.message) for warning in w)
    finally:
        os.environ["FLASK_ENV"] = "development"
        os.environ.pop("SECRET_KEY", None)


# ── 12. Histórico de status diferenciado ─────────────────────────────────────

def test_status_log_contains_details(app):
    with app.app_context():
        from app.models import create_ticket, update_status, get_logs
        tid = create_ticket({"tipo": "COMPRA", "titulo": "Log detalhe test",
                              "prioridade": "MEDIA"})
        update_status(tid, "EM_ANDAMENTO", "Iniciando atendimento urgente")
        logs = get_logs(tid)
        status_logs = [l for l in logs if l["evento"] == "STATUS_ALTERADO"]
        assert len(status_logs) >= 1
        assert "EM_ANDAMENTO" in status_logs[-1]["detalhe"]


# ── 13. Notificação ao devolver chamado ───────────────────────────────────────

def test_devolver_route_notifies_requester(app, auth):
    """Rota POST /tickets/<id>/devolver deve criar notificação interna."""
    with app.app_context():
        from app.models import create_ticket
        from app.db import get_db
        from app.services.user_service import create_user

        req_id = create_user("Req Notif", "req_notif@test.com", "r123", role="solicitante")
        tid = create_ticket({"tipo": "COMPRA", "titulo": "Devolucao notif test",
                              "prioridade": "MEDIA", "requester_user_id": req_id})

    r = auth.post(f"/tickets/{tid}/devolver",
                   data={"motivo_devolucao": "Precisa do número da NF"},
                   follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from app.db import get_db
        notif = get_db().execute(
            "SELECT * FROM notifications WHERE user_id=? AND ticket_id=?",
            (req_id, tid)
        ).fetchone()
        assert notif is not None
        assert "complemento" in notif["titulo"].lower() or notif["ticket_id"] == tid
