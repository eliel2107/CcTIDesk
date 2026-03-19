from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from app.services.auth_service import authenticate, get_user, ensure_default_admin
from app.extensions import limiter
# Fonte única de verdade: decorators vivem em auth/decorators.py.
from app.auth.decorators import login_required, role_required  # noqa: F401 — re-exportados

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.before_app_request
def load_logged_user():
    # init_db() é chamado uma única vez no startup via create_app() — não repetir aqui.
    user_id = session.get("user_id")
    # Converte sqlite3.Row para dict — permite .get(), json.dumps(), etc.
    raw = get_user(user_id) if user_id else None
    g.user = dict(raw) if raw else None

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"], error_message="Muitas tentativas de login. Aguarde 1 minuto.")
def login():
    if request.method == "POST":
        user = authenticate(request.form.get("email",""), request.form.get("password",""))
        if not user:
            flash("E-mail ou senha inválidos.", "error")
            return redirect(url_for("auth.login"))
        if "active" in user.keys() and int(user["active"]) != 1:
            flash("Usuário inativo. Procure um administrador.", "error")
            return redirect(url_for("auth.login"))
        session.clear()
        session["user_id"] = user["id"]
        flash("Login realizado com sucesso.", "success")
        return redirect(url_for("routes.dashboard"))
    return render_template("login.html")

@bp.post("/logout")
def logout():
    # POST evita que links externos forcem logout via GET (CSRF de logout forçado).
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("auth.login"))
