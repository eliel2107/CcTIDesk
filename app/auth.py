from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from app.db import init_db
from app.services.auth_service import authenticate, get_user, ensure_default_admin
from app.extensions import limiter

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.before_app_request
def load_logged_user():
    try:
        init_db()
    except Exception:
        pass
    ensure_default_admin()
    user_id = session.get("user_id")
    # Converte sqlite3.Row para dict — permite .get(), json.dumps(), etc.
    raw = get_user(user_id) if user_id else None
    g.user = dict(raw) if raw else None

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Faça login para acessar o sistema.", "error")
            return redirect(url_for("auth.login"))
        if "active" in g.user.keys() and int(g.user["active"]) != 1:
            session.clear()
            flash("Seu usuário está inativo.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Faça login para acessar o sistema.", "error")
                return redirect(url_for("auth.login"))
            if g.user["role"] not in roles:
                flash("Você não tem permissão para acessar esta área.", "error")
                return redirect(url_for("routes.dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

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

@bp.get("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("auth.login"))
