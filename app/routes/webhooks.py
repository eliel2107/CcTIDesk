"""Rotas de Webhooks."""

from flask import render_template, request, redirect, url_for, flash

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.services.webhook_service import list_webhooks, create_webhook, update_webhook, delete_webhook

WEBHOOK_EVENTS = [
    "ticket.criado", "ticket.assumido", "ticket.status_alterado",
    "ticket.finalizado", "ticket.concluido", "ticket.transferido",
    "ticket.aprovado", "ticket.reprovado",
]


@bp.get("/admin/webhooks")
@login_required
@role_required("admin")
def webhooks_list():
    return render_template("webhooks.html", hooks=list_webhooks(), WEBHOOK_EVENTS=WEBHOOK_EVENTS)


@bp.post("/admin/webhooks/novo")
@login_required
@role_required("admin")
def create_webhook_route():
    nome = request.form.get("nome", "").strip()
    url_hook = request.form.get("url", "").strip()
    eventos = request.form.getlist("eventos")
    secret = request.form.get("secret", "").strip()
    if not nome or not url_hook:
        flash("Nome e URL são obrigatórios.", "error")
        return redirect(url_for("routes.webhooks_list"))
    create_webhook(nome, url_hook, eventos, secret)
    flash(f"Webhook '{nome}' criado.", "success")
    return redirect(url_for("routes.webhooks_list"))


@bp.post("/admin/webhooks/<int:hook_id>/editar")
@login_required
@role_required("admin")
def edit_webhook_route(hook_id: int):
    update_webhook(hook_id, request.form.get("nome", ""), request.form.get("url", ""),
                   request.form.getlist("eventos"), request.form.get("ativo") == "1",
                   request.form.get("secret", ""))
    flash("Webhook atualizado.", "success")
    return redirect(url_for("routes.webhooks_list"))


@bp.post("/admin/webhooks/<int:hook_id>/excluir")
@login_required
@role_required("admin")
def delete_webhook_route(hook_id: int):
    delete_webhook(hook_id)
    flash("Webhook removido.", "success")
    return redirect(url_for("routes.webhooks_list"))
