"""Serviço de Comentários e Notas Internas."""

from app.db import get_db
from app.helpers import _now
from app.services.ticket_service import log_event


def add_comment(ticket_id: int, user_id: int, user_nome: str, conteudo: str, interno: bool = False) -> int:
    conteudo = (conteudo or "").strip()
    if not conteudo:
        raise ValueError("Conteúdo do comentário é obrigatório.")
    if len(conteudo) > 5000:
        raise ValueError("Comentário muito longo (máximo 5000 caracteres).")
    db = get_db()
    cur = db.execute(
        "INSERT INTO ticket_comments (ticket_id, user_id, user_nome, conteudo, interno, criado_em) VALUES (?,?,?,?,?,?)",
        (ticket_id, user_id, user_nome, conteudo, 1 if interno else 0, _now())
    )
    db.commit()
    evento = "NOTA_INTERNA" if interno else "COMENTARIO"
    log_event(ticket_id, evento, f"{user_nome}: {conteudo[:80]}")
    return cur.lastrowid


def get_comments(ticket_id: int, include_internal: bool = True):
    db = get_db()
    if include_internal:
        return db.execute(
            "SELECT * FROM ticket_comments WHERE ticket_id=? ORDER BY criado_em ASC", (ticket_id,)
        ).fetchall()
    return db.execute(
        "SELECT * FROM ticket_comments WHERE ticket_id=? AND interno=0 ORDER BY criado_em ASC", (ticket_id,)
    ).fetchall()


def delete_comment(comment_id: int, user_id: int, user_role: str = ""):
    db = get_db()
    if user_role == "admin":
        db.execute("DELETE FROM ticket_comments WHERE id=?", (comment_id,))
    else:
        db.execute("DELETE FROM ticket_comments WHERE id=? AND user_id=?", (comment_id, user_id))
    db.commit()
