"""Rotas de Fila e Kanban."""

from flask import render_template, request, redirect, url_for, flash, g, current_app

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.db import get_db
from app.constants import QUEUE_VISIBLE_STATUSES, TYPES
from app.helpers import _today_ymd
from app.services.ticket_service import list_queue_tickets, assign_ticket, get_ticket
from app.services.category_service import list_categories, get_user_categories
from app.notifications import on_ticket_assumido
from app.notify import notify_ticket_assigned


@bp.get("/fila")
@login_required
@role_required('admin', 'operador')
def queue():
    filters = {k: request.args.get(k, "") for k in ["status", "tipo", "q", "only_unassigned", "categoria_id"]}
    tickets = list_queue_tickets(filters, user_id=g.user["id"], user_role=g.user["role"])
    categories = list_categories(only_active=True)
    user_cat_ids = get_user_categories(g.user["id"]) if g.user["role"] == "operador" else []
    return render_template("queue.html", tickets=tickets, STATUSES=QUEUE_VISIBLE_STATUSES, TYPES=TYPES,
                           filters=filters, categories=categories, user_cat_ids=user_cat_ids,
                           assignment_timeout_minutes=current_app.config.get("ASSIGNMENT_TIMEOUT_MINUTES", 15))


@bp.post("/fila/<int:ticket_id>/assumir")
@login_required
@role_required('admin', 'operador')
def take_ticket(ticket_id: int):
    try:
        assign_ticket(ticket_id, g.user["id"], g.user["nome"])
        _t = get_ticket(ticket_id)
        if _t:
            from app.services.auth_service import get_user
            _req = get_user(_t["requester_user_id"]) if _t["requester_user_id"] else None
            notify_ticket_assigned(current_app.config, ticket_id=ticket_id, titulo=_t["titulo"],
                                   responsavel=g.user["nome"],
                                   requester_email=_req["email"] if _req else None)
            if _t["requester_user_id"]:
                on_ticket_assumido(ticket_id, _t["titulo"], _t["requester_user_id"], g.user["nome"])
        flash("Chamado assumido. Iniciando atendimento.", "success")
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("routes.queue"))
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.get("/kanban")
@login_required
def kanban():
    db = get_db()
    stats_today = _today_ymd()
    statuses = [
        ("ABERTO", "Aberto"), ("EM_ANDAMENTO", "Em andamento"),
        ("AGUARDANDO_FORNECEDOR", "Aguardando fornecedor"),
        ("AGUARDANDO_APROVACAO", "Aguardando aprovação"),
        ("ENVIADO", "Enviado"), ("CONCLUIDO", "Concluído"), ("CANCELADO", "Cancelado"),
    ]
    user_role = g.user["role"]
    uid = g.user["id"]

    if user_role == "operador":
        allowed_cats = db.execute("SELECT category_id FROM user_categories WHERE user_id=?", (uid,)).fetchall()
        cat_ids = [r["category_id"] for r in allowed_cats]
        if cat_ids:
            placeholders = ",".join("?" * len(cat_ids))
            rows = db.execute(
                f"""SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em
                    FROM tickets WHERE categoria_id IN ({placeholders}) ORDER BY atualizado_em DESC""", cat_ids
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em FROM tickets WHERE assigned_user_id=? ORDER BY atualizado_em DESC",
                (uid,)
            ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em FROM tickets ORDER BY atualizado_em DESC"
        ).fetchall()

    by_status = {s[0]: [] for s in statuses}
    for t in rows:
        by_status.setdefault(t["status"], []).append(t)
    columns = [{"status": s, "title": title, "cards": by_status.get(s, [])} for s, title in statuses]
    return render_template("kanban.html", columns=columns, stats_today=stats_today)
