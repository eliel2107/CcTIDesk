import os
from flask import Flask, jsonify, request
from flask_wtf.csrf import CSRFError

from .extensions import csrf, limiter
from .config import Config
from .db import init_app as init_db_app
from .cli import init_cli


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    cfg = Config()
    app.config.from_object(cfg)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "uploads"), exist_ok=True)
    os.makedirs(app.config.get("BACKUP_DIR", os.path.join(os.getcwd(), "instance", "backups")), exist_ok=True)

    # ── Sentry ────────────────────────────────────────────────────────────
    sentry_dsn = app.config.get("SENTRY_DSN", "")
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.1,
                send_default_pii=False,
            )
        except ImportError:
            app.logger.warning("sentry-sdk não instalado. Execute: pip install sentry-sdk")

    # ── Extensões ─────────────────────────────────────────────────────────
    app.config["WTF_CSRF_CHECK_DEFAULT"] = True
    csrf.init_app(app)
    limiter.init_app(app)

    # ── Tratamento global de CSRF inválido ────────────────────────────────
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        if best == "application/json" or request.is_json:
            return jsonify(error="CSRF token inválido ou expirado.", code=403), 403
        from flask import flash, redirect, url_for
        flash("Sessão expirada ou requisição inválida. Por favor, tente novamente.", "error")
        return redirect(request.referrer or url_for("auth.login"))

    # ── DB + CLI ──────────────────────────────────────────────────────────
    init_db_app(app)
    init_cli(app)

    # ── Jinja filters ─────────────────────────────────────────────────────
    import json as _json
    @app.template_filter("from_json")
    def from_json_filter(value):
        if not value:
            return []
        try:
            return _json.loads(value)
        except Exception:
            return []

    @app.template_filter("minutes_to_human")
    def minutes_to_human(minutes):
        if minutes is None:
            return "—"
        h, m = divmod(int(minutes), 60)
        if h > 0:
            return f"{h}h {m}min"
        return f"{m}min"

    # ── Scheduler (backup + digest + recorrência) ─────────────────────────
    _init_scheduler(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from .routes import bp as routes_bp
    from .auth import bp as auth_bp
    from .api import bp as api_bp
    from .admin import bp as admin_bp
    from .assets_admin import bp as assets_admin_bp
    from .reports import bp as reports_bp
    from .kb import bp as kb_bp
    from .portal import bp as portal_bp
    from .stock import bp as stock_bp
    from .nf import bp as nf_bp
    from .catalogo import bp as catalogo_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(assets_admin_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(portal_bp)
    csrf.exempt(portal_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(nf_bp)
    app.register_blueprint(catalogo_bp)
    app.register_blueprint(routes_bp)

    return app


def _init_scheduler(app):
    """Inicializa APScheduler com jobs de backup, digest e recorrência."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        import atexit
    except ImportError:
        app.logger.warning("APScheduler não instalado. Execute: pip install apscheduler")
        return

    scheduler = BackgroundScheduler(daemon=True)

    # Backup diário às 02:00
    @scheduler.scheduled_job(CronTrigger(hour=2, minute=0))
    def _job_backup():
        with app.app_context():
            from .scheduler import run_backup
            run_backup(app)

    # Digest matinal às 08:00
    @scheduler.scheduled_job(CronTrigger(hour=8, minute=0))
    def _job_digest():
        with app.app_context():
            from .scheduler import run_daily_digest
            run_daily_digest(app)

    # Chamados recorrentes — verifica a cada hora
    @scheduler.scheduled_job(CronTrigger(minute=0))
    def _job_recorrentes():
        with app.app_context():
            from .scheduler import run_recurring_tickets
            run_recurring_tickets()

    # Fallback de assunção — verifica a cada minuto
    @scheduler.scheduled_job(CronTrigger(minute="*"))
    def _job_assignment_timeout():
        with app.app_context():
            from .scheduler import run_assignment_timeout_fallback
            run_assignment_timeout_fallback(app)

    # Limpeza de rascunhos de NF cancelados — diariamente às 03:30
    @scheduler.scheduled_job(CronTrigger(hour=3, minute=30))
    def _job_nf_cleanup():
        with app.app_context():
            from .scheduler import run_nf_cleanup
            run_nf_cleanup(app)

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
