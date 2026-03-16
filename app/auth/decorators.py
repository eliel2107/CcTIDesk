"""Decorators de autenticação e autorização — importáveis sem circular import."""

from functools import wraps
from flask import session, g, flash, redirect, url_for


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
