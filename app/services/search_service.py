"""Serviço de Busca Avançada."""

from app.db import get_db
from app.helpers import _clean


def search_tickets_advanced(q: str = "", status: str = "", categoria_id: str = "",
                             classificacao: str = "", responsavel: str = "",
                             data_inicio: str = "", data_fim: str = "",
                             user_id: int = None, user_role: str = None,
                             limit: int = 50):
    db = get_db()
    sql = """SELECT t.id, t.numero_chamado, t.titulo, t.solicitante, t.responsavel,
                    t.prioridade, t.status, t.classificacao, t.data_limite, t.sla_deadline,
                    t.criado_em, t.atualizado_em, t.categoria_id,
                    c.nome as categoria_nome, c.cor as categoria_cor
             FROM tickets t
             LEFT JOIN categories c ON c.id=t.categoria_id
             WHERE 1=1"""
    params = []
    if user_role == "operador" and user_id:
        allowed = db.execute("SELECT category_id FROM user_categories WHERE user_id=?", (user_id,)).fetchall()
        aids = [r["category_id"] for r in allowed]
        if aids:
            sql += f" AND t.categoria_id IN ({','.join('?' * len(aids))})"; params.extend(aids)
    if q:
        like = f"%{q}%"
        sql += """ AND (t.titulo LIKE ? OR t.solicitante LIKE ? OR t.responsavel LIKE ?
                        OR t.numero_chamado LIKE ? OR t.descricao LIKE ?)"""
        params.extend([like] * 5)
    if status:
        sql += " AND t.status=?"; params.append(status)
    if categoria_id and str(categoria_id).isdigit():
        sql += " AND t.categoria_id=?"; params.append(int(categoria_id))
    if classificacao:
        sql += " AND t.classificacao=?"; params.append(classificacao)
    if responsavel:
        sql += " AND t.responsavel LIKE ?"; params.append(f"%{responsavel}%")
    if data_inicio:
        sql += " AND substr(t.criado_em,1,10) >= ?"; params.append(data_inicio)
    if data_fim:
        sql += " AND substr(t.criado_em,1,10) <= ?"; params.append(data_fim)
    sql += " ORDER BY t.atualizado_em DESC LIMIT ?"; params.append(limit)
    return db.execute(sql, params).fetchall()
