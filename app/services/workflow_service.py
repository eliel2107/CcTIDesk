"""Serviço de Fluxo de Trabalho — transferência, reabertura, devolução."""

from datetime import timedelta, datetime
from app.db import get_db
from app.helpers import _now, _parse_dt
from app.services.ticket_service import log_event, _log_asset_history


def transfer_ticket(ticket_id: int, para_user_id: int, para_user_nome: str,
                    de_user_id: int = None, de_user_nome: str = "", motivo: str = ""):
    db = get_db()
    t = db.execute("SELECT id, assigned_user_id, responsavel FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    db.execute(
        "UPDATE tickets SET assigned_user_id=?, responsavel=?, atualizado_em=? WHERE id=?",
        (para_user_id, para_user_nome, _now(), ticket_id)
    )
    db.execute(
        """INSERT INTO ticket_transfers
           (ticket_id, de_user_id, de_user_nome, para_user_id, para_user_nome, motivo, transferido_em)
           VALUES (?,?,?,?,?,?,?)""",
        (ticket_id, de_user_id, de_user_nome or "", para_user_id, para_user_nome, motivo, _now())
    )
    db.commit()
    log_event(ticket_id, "TRANSFERIDO", f"De '{de_user_nome or '?'}' para '{para_user_nome}'. {motivo}")


def get_transfers(ticket_id: int):
    return get_db().execute(
        "SELECT * FROM ticket_transfers WHERE ticket_id=? ORDER BY transferido_em DESC", (ticket_id,)
    ).fetchall()


def reabrir_ticket(ticket_id: int, user_nome: str = "", allow_override: bool = False):
    from flask import current_app
    from app.services.sla_service import calc_sla_deadline

    db = get_db()
    t = db.execute("SELECT id, status, closed_em, asset_id, numero_chamado, categoria_id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] not in ("CONCLUIDO", "CANCELADO"):
        raise ValueError("Apenas chamados concluídos ou cancelados podem ser reabertos.")

    window_h = int(current_app.config.get("TICKET_REOPEN_WINDOW_HOURS", 48) or 48)
    closed_at = _parse_dt(t["closed_em"])
    if not allow_override and closed_at:
        limite = closed_at + timedelta(hours=window_h)
        if datetime.now() > limite:
            raise ValueError(f"Prazo de reabertura expirado. Máximo {window_h}h após encerramento.")

    db.execute(
        "UPDATE tickets SET status='ABERTO', closed_em=NULL, reaberto_em=?, atualizado_em=? WHERE id=?",
        (_now(), _now(), ticket_id)
    )
    # Recalcular SLA
    cat_id = t["categoria_id"] if "categoria_id" in t.keys() else None
    if cat_id:
        new_sla = calc_sla_deadline(cat_id, _now())
        if new_sla:
            db.execute("UPDATE tickets SET sla_deadline=? WHERE id=?", (new_sla, ticket_id))
    db.commit()
    log_event(ticket_id, "REABERTO", f"Chamado reaberto por {user_nome}.")
    if t["asset_id"]:
        _log_asset_history(t["asset_id"], "REABERTO_CHAMADO",
                           f"Chamado {t['numero_chamado'] or ticket_id} foi reaberto por {user_nome}.")


def devolver_ao_solicitante(ticket_id: int, operador_nome: str, motivo: str):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] in ("CONCLUIDO", "CANCELADO"):
        raise ValueError("Chamado encerrado não pode ser devolvido.")
    db.execute(
        "UPDATE tickets SET status='AGUARDANDO_INFO', motivo_devolucao=?, atualizado_em=? WHERE id=?",
        (motivo.strip(), _now(), ticket_id)
    )
    db.commit()
    log_event(ticket_id, "DEVOLVIDO", f"Devolvido por {operador_nome}. Motivo: {motivo[:120]}")


def reenviar_pelo_solicitante(ticket_id: int, solicitante_nome: str, complemento: str = ""):
    db = get_db()
    t = db.execute("SELECT id, status, assigned_user_id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] != "AGUARDANDO_INFO":
        raise ValueError("Chamado não está aguardando informações.")
    novo_status = "EM_ANDAMENTO" if t["assigned_user_id"] else "ABERTO"
    db.execute(
        "UPDATE tickets SET status=?, motivo_devolucao=NULL, atualizado_em=? WHERE id=?",
        (novo_status, _now(), ticket_id)
    )
    db.commit()
    detalhe = f"Solicitante {solicitante_nome} complementou as informações e reenviou."
    if complemento:
        detalhe += f" Complemento: {complemento[:200]}"
    log_event(ticket_id, "REENVIADO", detalhe)
