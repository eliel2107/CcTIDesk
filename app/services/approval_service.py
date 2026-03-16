"""Serviço de Aprovação de chamados."""

from typing import Optional
from app.db import get_db
from app.helpers import _now, _parse_float
from app.services.ticket_service import log_event


def solicitar_aprovacao(ticket_id: int, solicitante_nome: str = ""):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    db.execute("UPDATE tickets SET status='AGUARDANDO_APROVACAO', atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    log_event(ticket_id, "AGUARDANDO_APROVACAO", f"Aprovação solicitada por {solicitante_nome}.")


def aprovar_ticket(ticket_id: int, aprovador_id: int, aprovador_nome: str):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] != "AGUARDANDO_APROVACAO":
        raise ValueError(
            f"Não é possível aprovar um chamado com status '{t['status']}'. "
            "Apenas chamados em 'AGUARDANDO_APROVACAO' podem ser aprovados."
        )
    t_now = _now()
    db.execute(
        "UPDATE tickets SET status='ABERTO', aprovado_por=?, aprovado_em=?, aprovador_user_id=?, atualizado_em=? WHERE id=?",
        (aprovador_nome, t_now, aprovador_id, t_now, ticket_id)
    )
    db.commit()
    log_event(ticket_id, "APROVADO", f"Aprovado por {aprovador_nome}.")


def reprovar_ticket(ticket_id: int, aprovador_nome: str, motivo: str = ""):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] != "AGUARDANDO_APROVACAO":
        raise ValueError(
            f"Não é possível reprovar um chamado com status '{t['status']}'. "
            "Apenas chamados em 'AGUARDANDO_APROVACAO' podem ser reprovados."
        )
    t_now = _now()
    db.execute(
        "UPDATE tickets SET status='CANCELADO', closed_em=?, aprovado_por=?, aprovado_em=?, atualizado_em=? WHERE id=?",
        (t_now, aprovador_nome, t_now, t_now, ticket_id)
    )
    db.commit()
    log_event(ticket_id, "REPROVADO", f"Reprovado por {aprovador_nome}. {motivo}")
    try:
        from app.services.stock_service import reverter_saidas_chamado
        reverter_saidas_chamado(ticket_id, usuario=aprovador_nome)
    except Exception:
        pass


def precisa_aprovacao(ticket_id: int) -> bool:
    db = get_db()
    row = db.execute(
        """SELECT c.requer_aprovacao, c.valor_aprovacao_limite, t.valor_estimado
           FROM tickets t LEFT JOIN categories c ON c.id=t.categoria_id
           WHERE t.id=?""", (ticket_id,)
    ).fetchone()
    if not row or not row["requer_aprovacao"]:
        return False
    limite = row["valor_aprovacao_limite"]
    if limite and row["valor_estimado"]:
        return float(row["valor_estimado"]) >= float(limite)
    return bool(row["requer_aprovacao"])
