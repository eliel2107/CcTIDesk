"""Serviço de Categorias de Chamados."""

from app.db import get_db
from app.helpers import _now


def list_categories(only_active: bool = False):
    db = get_db()
    q = "SELECT id, nome, descricao, cor, ativo, campos_visiveis, criado_em FROM categories"
    if only_active:
        q += " WHERE ativo=1"
    q += " ORDER BY nome ASC"
    return db.execute(q).fetchall()


def get_category(category_id: int):
    return get_db().execute(
        "SELECT id, nome, descricao, cor, ativo, campos_visiveis, criado_em FROM categories WHERE id=?",
        (category_id,)
    ).fetchone()


def create_category(nome: str, descricao: str = "", cor: str = "#6366f1", campos_visiveis: str = None) -> int:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome da categoria é obrigatório.")
    db = get_db()
    cur = db.execute(
        "INSERT INTO categories (nome, descricao, cor, ativo, campos_visiveis, criado_em) VALUES (?, ?, ?, 1, ?, ?)",
        (nome, (descricao or "").strip(), cor or "#6366f1", campos_visiveis, _now())
    )
    db.commit()
    return cur.lastrowid


def update_category(category_id: int, nome: str, descricao: str, cor: str, ativo: bool, campos_visiveis: str = None):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome da categoria é obrigatório.")
    db = get_db()
    db.execute(
        "UPDATE categories SET nome=?, descricao=?, cor=?, ativo=?, campos_visiveis=? WHERE id=?",
        (nome, (descricao or "").strip(), cor or "#6366f1", 1 if ativo else 0, campos_visiveis, category_id)
    )
    db.commit()


def delete_category(category_id: int):
    db = get_db()
    db.execute("UPDATE tickets SET categoria_id=NULL WHERE categoria_id=?", (category_id,))
    db.execute("DELETE FROM user_categories WHERE category_id=?", (category_id,))
    db.execute("DELETE FROM categories WHERE id=?", (category_id,))
    db.commit()


def get_user_categories(user_id: int):
    rows = get_db().execute(
        "SELECT category_id FROM user_categories WHERE user_id=?", (user_id,)
    ).fetchall()
    return [r["category_id"] for r in rows]


def set_user_categories(user_id: int, category_ids):
    db = get_db()
    db.execute("DELETE FROM user_categories WHERE user_id=?", (user_id,))
    for cid in category_ids:
        db.execute("INSERT OR IGNORE INTO user_categories (user_id, category_id) VALUES (?, ?)", (user_id, cid))
    db.commit()


def create_category_full(nome: str, descricao: str = "", cor: str = "#6366f1",
                          campos_visiveis: str = None, sla_horas: int = None,
                          checklist_padrao: str = None, template_descricao: str = None,
                          requer_aprovacao: bool = False, valor_aprovacao_limite: float = None,
                          prioridade_padrao: str = None) -> int:
    db = get_db()
    cur = db.execute(
        """INSERT INTO categories (nome, descricao, cor, ativo, campos_visiveis, sla_horas,
           checklist_padrao, template_descricao, requer_aprovacao, valor_aprovacao_limite, prioridade_padrao, criado_em)
           VALUES (?,?,?,1,?,?,?,?,?,?,?,?)""",
        (nome, descricao, cor, campos_visiveis, sla_horas,
         checklist_padrao, template_descricao,
         1 if requer_aprovacao else 0, valor_aprovacao_limite, prioridade_padrao, _now())
    )
    db.commit()
    return cur.lastrowid


def update_category_full(category_id: int, nome: str, descricao: str, cor: str, ativo: bool,
                          campos_visiveis: str = None, sla_horas: int = None,
                          checklist_padrao: str = None, template_descricao: str = None,
                          requer_aprovacao: bool = False, valor_aprovacao_limite: float = None,
                          prioridade_padrao: str = None):
    db = get_db()
    db.execute(
        """UPDATE categories SET nome=?, descricao=?, cor=?, ativo=?, campos_visiveis=?,
           sla_horas=?, checklist_padrao=?, template_descricao=?, requer_aprovacao=?,
           valor_aprovacao_limite=?, prioridade_padrao=? WHERE id=?""",
        (nome, descricao, cor, 1 if ativo else 0, campos_visiveis,
         sla_horas, checklist_padrao, template_descricao,
         1 if requer_aprovacao else 0, valor_aprovacao_limite, prioridade_padrao, category_id)
    )
    db.commit()
