"""
Portal externo — acesso via token sem login.
Solicitantes externos acompanham, confirmam e complementam chamados por link.
"""
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from .db import get_db
from .extensions import limiter
from .models import (
    get_ticket, get_logs, get_comments, list_attachments,
    confirmar_conclusao, rejeitar_conclusao,
    reenviar_pelo_solicitante, add_comment, _now,
)

bp = Blueprint("portal", __name__, url_prefix="/portal")


def create_portal_token(ticket_id: int, email: str = "", expira_horas: int = 720) -> str:
    """Gera e salva um token de acesso ao chamado. Retorna o token."""
    token = secrets.token_urlsafe(32)
    db = get_db()
    expira_em = (datetime.now() + timedelta(hours=expira_horas)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO portal_tokens (token, ticket_id, email, criado_em, expira_em) VALUES (?,?,?,?,?)",
        (token, ticket_id, email, _now(), expira_em)
    )
    db.commit()
    return token


def _resolve_token(token: str):
    """Retorna (token_row, ticket) ou (None, None) se inválido/expirado."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM portal_tokens WHERE token=?", (token,)
    ).fetchone()
    if not row:
        return None, None
    if row["expira_em"] and datetime.now() > datetime.strptime(row["expira_em"], "%Y-%m-%d %H:%M:%S"):
        return None, None
    ticket = get_ticket(row["ticket_id"])
    return row, ticket


# ── Rotas ─────────────────────────────────────────────────────────────────────

@bp.get("/<token>")
def portal_view(token: str):
    tok, ticket = _resolve_token(token)
    if not tok or not ticket:
        abort(404)
    logs = get_logs(ticket["id"])
    comments = get_comments(ticket["id"], include_internal=False)
    attachments = list_attachments(ticket["id"])
    return render_template("portal.html", ticket=ticket, logs=logs,
                            comments=comments, attachments=attachments, token=token)


@bp.post("/<token>/confirmar")
@limiter.limit("10 per minute")
def portal_confirmar(token: str):
    tok, ticket = _resolve_token(token)
    if not tok or not ticket:
        abort(404)
    try:
        confirmar_conclusao(ticket["id"], tok["email"] or "solicitante externo")
        flash("✅ Conclusão confirmada! Obrigado.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("portal.portal_view", token=token))


@bp.post("/<token>/rejeitar")
@limiter.limit("10 per minute")
def portal_rejeitar(token: str):
    tok, ticket = _resolve_token(token)
    if not tok or not ticket:
        abort(404)
    motivo = request.form.get("motivo", "")
    try:
        rejeitar_conclusao(ticket["id"], motivo, tok["email"] or "solicitante externo")
        flash("Conclusão rejeitada. O operador será notificado.", "info")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("portal.portal_view", token=token))


@bp.post("/<token>/comentar")
@limiter.limit("20 per minute")
def portal_comentar(token: str):
    tok, ticket = _resolve_token(token)
    if not tok or not ticket:
        abort(404)
    conteudo = request.form.get("conteudo", "").strip()
    if not conteudo:
        flash("Comentário não pode estar vazio.", "error")
        return redirect(url_for("portal.portal_view", token=token))
    nome = tok["email"] or "Solicitante externo"
    # user_id=0 para externos; usa variável local para garantir mesma conexão.
    db = get_db()
    db.execute(
        "INSERT INTO ticket_comments (ticket_id, user_id, user_nome, conteudo, interno, criado_em) VALUES (?,0,?,?,0,?)",
        (ticket["id"], nome, conteudo, _now())
    )
    db.commit()
    from .models import log_event
    log_event(ticket["id"], "COMENTARIO_EXTERNO", f"{nome}: {conteudo[:80]}")
    flash("Mensagem enviada.", "success")
    return redirect(url_for("portal.portal_view", token=token))


@bp.post("/<token>/reenviar")
@limiter.limit("10 per minute")
def portal_reenviar(token: str):
    tok, ticket = _resolve_token(token)
    if not tok or not ticket:
        abort(404)
    complemento = request.form.get("complemento", "").strip()
    if not complemento:
        flash("Adicione as informações antes de reenviar.", "error")
        return redirect(url_for("portal.portal_view", token=token))
    try:
        add_comment(ticket["id"], 0, tok["email"] or "Solicitante externo",
                    f"[Complemento via portal]\n{complemento}", interno=False)
        reenviar_pelo_solicitante(ticket["id"], tok["email"] or "Solicitante externo", complemento)
        flash("Informações enviadas com sucesso!", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("portal.portal_view", token=token))
