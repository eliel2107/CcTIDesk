"""Serviço de Grupos de Operadores."""

from typing import Optional
from app.db import get_db
from app.helpers import _now
from app.services.ticket_service import assign_ticket


def list_groups():
    return get_db().execute("SELECT * FROM operator_groups ORDER BY nome").fetchall()


def get_group(group_id: int):
    return get_db().execute("SELECT * FROM operator_groups WHERE id=?", (group_id,)).fetchone()


def create_group(nome: str, descricao: str = "", cor: str = "#6366f1") -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO operator_groups (nome, descricao, cor, ativo, criado_em) VALUES (?,?,?,1,?)",
        (nome, descricao, cor, _now())
    )
    db.commit()
    return cur.lastrowid


def update_group(group_id: int, nome: str, descricao: str, cor: str, ativo: bool):
    db = get_db()
    db.execute("UPDATE operator_groups SET nome=?, descricao=?, cor=?, ativo=? WHERE id=?",
               (nome, descricao, cor, 1 if ativo else 0, group_id))
    db.commit()


def set_group_members(group_id: int, user_ids):
    db = get_db()
    db.execute("DELETE FROM group_members WHERE group_id=?", (group_id,))
    for uid in user_ids:
        db.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?,?)", (group_id, uid))
    db.commit()


def set_group_categories(group_id: int, category_ids):
    db = get_db()
    db.execute("DELETE FROM group_categories WHERE group_id=?", (group_id,))
    for cid in category_ids:
        db.execute("INSERT OR IGNORE INTO group_categories (group_id, category_id) VALUES (?,?)", (group_id, cid))
    db.commit()


def get_group_members(group_id: int):
    return get_db().execute(
        """SELECT u.id, u.nome, u.email, u.role FROM users u
           JOIN group_members gm ON gm.user_id=u.id WHERE gm.group_id=?""", (group_id,)
    ).fetchall()


def get_group_categories(group_id: int):
    return get_db().execute(
        """SELECT c.id, c.nome, c.cor FROM categories c
           JOIN group_categories gc ON gc.category_id=c.id WHERE gc.group_id=?""", (group_id,)
    ).fetchall()


def assign_ticket_to_group(ticket_id: int, group_id: int) -> Optional[dict]:
    db = get_db()
    members = db.execute(
        """SELECT u.id, u.nome,
           (SELECT COUNT(*) FROM tickets t WHERE t.assigned_user_id=u.id
            AND t.status NOT IN ('CONCLUIDO','CANCELADO')) as carga
           FROM users u
           JOIN group_members gm ON gm.user_id=u.id
           WHERE gm.group_id=? AND u.active=1
           ORDER BY carga ASC, u.nome ASC LIMIT 1""", (group_id,)
    ).fetchone()
    if not members:
        return None
    assign_ticket(ticket_id, members["id"], members["nome"])
    return dict(members)
