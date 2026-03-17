"""Rotas de Fluxo — finalizar, confirmar, rejeitar, reabrir, devolver, transferir."""

from flask import request, redirect, url_for, flash, g, current_app

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.services.ticket_service import get_ticket, finalizar_ticket, confirmar_conclusao, rejeitar_conclusao, assign_ticket
from app.services.workflow_service import transfer_ticket, reabrir_ticket, devolver_ao_solicitante, reenviar_pelo_solicitante
from app.services.comment_service import add_comment
from app.notifications import (
    on_aguardando_confirmacao, on_conclusao_rejeitada, on_chamado_concluido, on_transferencia,
    criar_notificacao,
)


@bp.post("/tickets/<int:ticket_id>/finalizar")
@login_required
@role_required('admin', 'operador')
def finalizar_ticket_route(ticket_id: int):
    try:
        _t = get_ticket(ticket_id)
        finalizar_ticket(ticket_id, g.user["nome"])
        if _t and _t["requester_user_id"]:
            on_aguardando_confirmacao(ticket_id, _t["titulo"], _t["requester_user_id"], g.user["nome"])
        flash("Chamado enviado para confirmação de quem abriu.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/confirmar")
@login_required
def confirmar_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    if g.user["role"] not in ("admin",) and t["requester_user_id"] != g.user["id"]:
        flash("Apenas quem abriu o chamado pode confirmar a conclusão.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    try:
        confirmar_conclusao(ticket_id, g.user["nome"])
        on_chamado_concluido(ticket_id, t["titulo"], t["requester_user_id"], t["assigned_user_id"], g.user["nome"])
        flash("Chamado concluído com sucesso!", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/rejeitar")
@login_required
def rejeitar_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    if g.user["role"] not in ("admin",) and t["requester_user_id"] != g.user["id"]:
        flash("Apenas quem abriu o chamado pode rejeitar a conclusão.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    try:
        motivo = request.form.get("motivo", "")
        rejeitar_conclusao(ticket_id, motivo, g.user["nome"])
        if t["assigned_user_id"]:
            on_conclusao_rejeitada(ticket_id, t["titulo"], t["assigned_user_id"], g.user["nome"], motivo)
        flash("Conclusão rejeitada. O chamado voltou para atendimento.", "info")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/transferir")
@login_required
@role_required("admin", "operador")
def transfer_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    para_user_id = request.form.get("para_user_id", "")
    motivo = request.form.get("motivo", "")
    if not para_user_id or not para_user_id.isdigit():
        flash("Selecione um operador para transferir.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    from app.services.auth_service import get_user
    dest = get_user(int(para_user_id))
    if not dest:
        flash("Operador não encontrado.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    if dest["role"] not in ("admin", "operador"):
        flash(f"'{dest['nome']}' é um solicitante e não pode receber chamados.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    if not dest["active"]:
        flash(f"'{dest['nome']}' está inativo.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    try:
        transfer_ticket(ticket_id, int(para_user_id), dest["nome"], g.user["id"], g.user["nome"], motivo)
        on_transferencia(ticket_id, t["titulo"], int(para_user_id), g.user["nome"])
        flash(f"Chamado transferido para {dest['nome']}.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/reabrir")
@login_required
def reabrir_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    if g.user["role"] != "admin" and t["requester_user_id"] != g.user["id"]:
        flash("Apenas quem abriu o chamado ou um admin pode reabri-lo.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    try:
        reabrir_ticket(ticket_id, g.user["nome"], allow_override=(g.user["role"] == "admin"))
        flash("Chamado reaberto com sucesso.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/devolver")
@login_required
@role_required("admin", "operador")
def devolver_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    motivo = request.form.get("motivo_devolucao", "").strip()
    if not motivo:
        flash("Informe o motivo da devolução.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    try:
        devolver_ao_solicitante(ticket_id, g.user["nome"], motivo)
        if t["requester_user_id"]:
            criar_notificacao(t["requester_user_id"], "AGUARDANDO_INFO",
                              f"Seu chamado precisa de complemento: {t['titulo']}",
                              f"{g.user['nome']} devolveu seu chamado. Motivo: {motivo[:120]}", ticket_id)
        flash("Chamado devolvido ao solicitante.", "info")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/reenviar")
@login_required
def reenviar_ticket_route(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.my_tickets"))
    if t["requester_user_id"] != g.user["id"] and g.user["role"] != "admin":
        flash("Apenas quem abriu o chamado pode reenviar.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    complemento = request.form.get("complemento", "").strip()
    if not complemento:
        flash("Adicione as informações solicitadas.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    try:
        add_comment(ticket_id, g.user["id"], g.user["nome"], f"[Complemento de informações]\n{complemento}", interno=False)
        reenviar_pelo_solicitante(ticket_id, g.user["nome"], complemento)
        if t["assigned_user_id"]:
            criar_notificacao(t["assigned_user_id"], "CHAMADO_REENVIADO",
                              f"Chamado complementado: {t['titulo']}",
                              f"{g.user['nome']} adicionou informações e reenviou.", ticket_id)
        flash("Informações enviadas!", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))


@bp.post("/tickets/<int:ticket_id>/gerar-token")
@login_required
@role_required("admin", "operador")
def gerar_portal_token(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    from app.portal import create_portal_token
    email = request.form.get("email", "").strip()
    token = create_portal_token(ticket_id, email=email, expira_horas=720)
    app_url = current_app.config.get("APP_URL", request.host_url.rstrip("/"))
    link = f"{app_url.rstrip('/')}/portal/{token}"
    flash(f"Link gerado: {link}", "success")
    if email:
        from app.notify import notify_async
        body = (f"Olá,\n\nVocê pode acompanhar seu chamado pelo link abaixo:\n\n  {link}\n\n"
                f"Chamado: {t['titulo']}\nNúmero: {t['numero_chamado'] or '#' + str(ticket_id)}\n\nO link é válido por 30 dias.")
        notify_async(dict(current_app.config), [email],
                     f"[CCTI] Acompanhe seu chamado {t['numero_chamado'] or '#' + str(ticket_id)}", body)
        flash(f"Link enviado para {email}.", "info")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
