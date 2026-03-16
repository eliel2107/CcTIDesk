"""Rotas de Comentários."""

from flask import request, redirect, url_for, flash, g

from app.routes import bp
from app.auth.decorators import login_required
from app.services.ticket_service import get_ticket
from app.services.comment_service import add_comment, delete_comment


@bp.post("/tickets/<int:ticket_id>/comentarios")
@login_required
def add_comment_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    conteudo = request.form.get("conteudo", "").strip()
    if not conteudo:
        flash("Comentário não pode estar vazio.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    interno = request.form.get("interno") == "1" and g.user["role"] in ("admin", "operador")
    add_comment(ticket_id, g.user["id"], g.user["nome"], conteudo, interno)
    flash("Comentário adicionado.", "success")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id) + "#comentarios")


@bp.post("/tickets/<int:ticket_id>/comentarios/<int:comment_id>/excluir")
@login_required
def delete_comment_route(ticket_id: int, comment_id: int):
    delete_comment(comment_id, g.user["id"], user_role=g.user["role"])
    flash("Comentário removido.", "success")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id) + "#comentarios")
