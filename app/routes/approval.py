"""Rotas de Aprovação."""

from flask import render_template, request, redirect, url_for, flash, g

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.db import get_db
from app.services.ticket_service import get_ticket
from app.services.approval_service import aprovar_ticket, reprovar_ticket
from app.notifications import on_chamado_aprovado, on_chamado_reprovado


@bp.get("/aprovacoes")
@login_required
@role_required("admin")
def aprovacoes():
    db = get_db()
    pendentes = db.execute(
        """SELECT t.*, c.nome as categoria_nome, c.cor as categoria_cor
           FROM tickets t LEFT JOIN categories c ON c.id=t.categoria_id
           WHERE t.status='AGUARDANDO_APROVACAO' ORDER BY t.criado_em ASC"""
    ).fetchall()
    return render_template("aprovacoes.html", tickets=pendentes)


@bp.post("/tickets/<int:ticket_id>/aprovar")
@login_required
@role_required("admin")
def aprovar_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.aprovacoes"))
    try:
        aprovar_ticket(ticket_id, g.user["id"], g.user["nome"])
        if t["requester_user_id"]:
            on_chamado_aprovado(ticket_id, t["titulo"], t["requester_user_id"], g.user["nome"])
        flash("Chamado aprovado e enviado para a fila.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.aprovacoes"))


@bp.post("/tickets/<int:ticket_id>/reprovar")
@login_required
@role_required("admin")
def reprovar_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.aprovacoes"))
    motivo = request.form.get("motivo", "")
    try:
        reprovar_ticket(ticket_id, g.user["nome"], motivo)
        if t["requester_user_id"]:
            on_chamado_reprovado(ticket_id, t["titulo"], t["requester_user_id"], g.user["nome"])
        flash("Chamado reprovado.", "info")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.aprovacoes"))
