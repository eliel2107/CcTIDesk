import os
from flask import Flask, jsonify, request
from flask_wtf.csrf import CSRFError

from .extensions import csrf, limiter
from .config import Config
from .db import init_app as init_db_app
from .cli import init_cli


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config())

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "uploads"), exist_ok=True)

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

    # ── Blueprints (importados aqui para evitar circular import) ──────────
    from .routes import bp as routes_bp
    from .auth import bp as auth_bp
    from .api import bp as api_bp
    from .admin import bp as admin_bp
    from .assets_admin import bp as assets_admin_bp
    from .reports import bp as reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)   # API usa JSON, não formulários HTML
    app.register_blueprint(admin_bp)
    app.register_blueprint(assets_admin_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(routes_bp)

    return app
