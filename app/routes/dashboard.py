"""Rotas de Dashboard, Home e Listagem principal."""

from flask import render_template, request, redirect, url_for, g, current_app

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.db import get_db
from app.constants import STATUSES, TYPES, PRIORITIES
from app.helpers import _today_ymd
from app.services.ticket_service import list_tickets_paginated
from app.services.dashboard_service import dashboard_stats_advanced
from app.services.category_service import get_user_categories


@bp.get("/")
@login_required
def index():
    filters = {k: request.args.get(k, "") for k in ["status", "tipo", "prioridade", "responsavel", "q", "sort_by", "asset_id", "show_archived"]}
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 25
    tickets, total, total_pages = list_tickets_paginated(
        filters, page=page, per_page=per_page,
        user_id=g.user["id"] if g.user else None,
        user_role=g.user["role"] if g.user else None,
    )
    grouped_tickets = []
    if g.user and g.user["role"] == "admin":
        grouped = {}
        for t in tickets:
            grouped.setdefault(t["categoria_nome"] or "Sem categoria", []).append(t)
        grouped_tickets = [{"categoria": k, "tickets": v} for k, v in grouped.items()]
    stats_today = _today_ymd()
    return render_template(
        "index.html",
        tickets=tickets, grouped_tickets=grouped_tickets,
        STATUSES=STATUSES, TYPES=TYPES, PRIORITIES=PRIORITIES,
        filters=filters, stats_today=stats_today,
        page=page, total=total, total_pages=total_pages, per_page=per_page,
        user_role=g.user["role"] if g.user else None,
    )


@bp.get("/dashboard")
@login_required
def dashboard():
    if g.user and g.user["role"] == "solicitante":
        return redirect(url_for("routes.my_tickets"))
    stats = dashboard_stats_advanced(
        user_id=g.user["id"] if g.user else None,
        user_role=g.user["role"] if g.user else None,
    )
    return render_template("dashboard.html", stats=stats, STATUSES=STATUSES,
                           user_role=g.user["role"] if g.user else None,
                           user_nome=g.user["nome"] if g.user else None)


@bp.get("/home")
@login_required
def executive_home():
    db = get_db()
    open_count = db.execute("SELECT COUNT(*) as c FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO')").fetchone()["c"]
    overdue_count = db.execute("SELECT COUNT(*) as c FROM tickets WHERE data_limite IS NOT NULL AND data_limite < date('now') AND status NOT IN ('CONCLUIDO','CANCELADO')").fetchone()["c"]
    asset_total = db.execute("SELECT COUNT(*) as c FROM assets").fetchone()["c"] if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'").fetchone() else 0
    assets_in_transit = db.execute("SELECT COUNT(*) as c FROM assets WHERE status='EM_TRANSITO'").fetchone()["c"] if asset_total >= 0 else 0
    assets_without_owner = db.execute("SELECT COUNT(*) as c FROM assets WHERE COALESCE(TRIM(responsavel),'')=''").fetchone()["c"] if asset_total >= 0 else 0
    return render_template("home_exec.html", open_count=open_count, overdue_count=overdue_count,
                           asset_total=asset_total, assets_in_transit=assets_in_transit,
                           assets_without_owner=assets_without_owner)
