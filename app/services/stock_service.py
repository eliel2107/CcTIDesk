from datetime import datetime
from app.db import get_db

CATEGORIAS = ["PERIFERICO", "CABO_ADAPTADOR", "REDE", "ESCRITORIO", "LIMPEZA", "EMBALAGEM", "OUTRO"]
CATEGORIAS_LABEL = {
    "PERIFERICO":    "Periférico",
    "CABO_ADAPTADOR":"Cabo / Adaptador",
    "REDE":          "Rede",
    "ESCRITORIO":    "Escritório",
    "LIMPEZA":       "Limpeza",
    "EMBALAGEM":     "Embalagem",
    "OUTRO":         "Outro",
}
UNIDADES = ["unidade", "caixa", "par", "rolo", "pacote", "litro", "metro"]

TIPO_ENTRADA = "ENTRADA"
TIPO_SAIDA   = "SAIDA"
TIPO_AJUSTE  = "AJUSTE"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Produtos ───────────────────────────────────────────────────────────

def list_produtos(filtros=None):
    filtros = filtros or {}
    db = get_db()
    q = """
        SELECT p.*,
               CASE WHEN p.quantidade_atual <= p.quantidade_minima AND p.quantidade_minima > 0
                    THEN 1 ELSE 0 END as alerta
        FROM stock_produtos p WHERE 1=1
    """
    params = []
    if filtros.get("q"):
        like = f"%{filtros['q']}%"
        q += " AND (p.nome LIKE ? OR p.categoria LIKE ? OR p.localizacao LIKE ?)"
        params.extend([like, like, like])
    if filtros.get("categoria"):
        q += " AND p.categoria = ?"
        params.append(filtros["categoria"])
    if filtros.get("alerta") == "1":
        q += " AND p.quantidade_atual <= p.quantidade_minima AND p.quantidade_minima > 0"
    if filtros.get("inativos") != "1":
        q += " AND p.ativo = 1"
    q += " ORDER BY alerta DESC, p.nome ASC"
    return db.execute(q, params).fetchall()


def get_produto(produto_id: int):
    return get_db().execute(
        "SELECT * FROM stock_produtos WHERE id = ?", (produto_id,)
    ).fetchone()


def create_produto(data: dict):
    nome = (data.get("nome") or "").strip()
    if not nome:
        raise ValueError("Nome do produto é obrigatório.")
    categoria = (data.get("categoria") or "OUTRO").strip().upper()
    descricao = (data.get("descricao") or "").strip()
    unidade = (data.get("unidade") or "unidade").strip()
    localizacao = (data.get("localizacao") or "").strip()
    qtd_inicial = max(0, int(data.get("quantidade_inicial") or 0))
    qtd_min = max(0, int(data.get("quantidade_minima") or 0))

    db = get_db()
    t = _now()
    cur = db.execute(
        """INSERT INTO stock_produtos
           (nome, categoria, descricao, unidade, localizacao,
            quantidade_atual, quantidade_minima, ativo, criado_em, atualizado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (nome, categoria, descricao, unidade, localizacao, qtd_inicial, qtd_min, t, t),
    )
    produto_id = cur.lastrowid

    if qtd_inicial > 0:
        db.execute(
            """INSERT INTO stock_movimentacoes
               (produto_id, tipo, quantidade, motivo, ticket_id, usuario, criado_em)
               VALUES (?, ?, ?, ?, NULL, ?, ?)""",
            (produto_id, TIPO_ENTRADA, qtd_inicial, "Estoque inicial", data.get("usuario"), t),
        )
    db.commit()
    return produto_id


def update_produto(produto_id: int, data: dict):
    p = get_produto(produto_id)
    if not p:
        raise ValueError("Produto não encontrado.")
    nome = (data.get("nome") or "").strip()
    if not nome:
        raise ValueError("Nome é obrigatório.")
    db = get_db()
    db.execute(
        """UPDATE stock_produtos
           SET nome=?, categoria=?, descricao=?, unidade=?, localizacao=?,
               quantidade_minima=?, ativo=?, atualizado_em=?
           WHERE id=?""",
        (
            nome,
            (data.get("categoria") or "OUTRO").strip().upper(),
            (data.get("descricao") or "").strip(),
            (data.get("unidade") or "unidade").strip(),
            (data.get("localizacao") or "").strip(),
            max(0, int(data.get("quantidade_minima") or 0)),
            1 if data.get("ativo") else 0,
            _now(),
            produto_id,
        ),
    )
    db.commit()


# ── Movimentações ──────────────────────────────────────────────────────

def registrar_movimentacao(produto_id: int, tipo: str, quantidade: int,
                           motivo: str = "", ticket_id=None, usuario: str = ""):
    p = get_produto(produto_id)
    if not p:
        raise ValueError("Produto não encontrado.")
    quantidade = int(quantidade)
    if quantidade <= 0:
        raise ValueError("Quantidade deve ser positiva.")

    if tipo == TIPO_SAIDA and p["quantidade_atual"] < quantidade:
        raise ValueError(
            f"Estoque insuficiente. Disponível: {p['quantidade_atual']} {p['unidade']}(s)."
        )

    db = get_db()
    t = _now()

    if tipo == TIPO_AJUSTE:
        # Ajuste é absoluto — seta nova quantidade e registra a diferença real para rastreio
        qtd_anterior = p["quantidade_atual"]
        diferenca = quantidade - qtd_anterior
        db.execute(
            "UPDATE stock_produtos SET quantidade_atual=?, atualizado_em=? WHERE id=?",
            (quantidade, t, produto_id),
        )
        # A movimentação guarda a diferença real (pode ser negativa) para o histórico ser legível
        motivo_ajuste = motivo or f"Ajuste manual: {qtd_anterior} → {quantidade} (diferença: {diferenca:+d})"
        db.execute(
            """INSERT INTO stock_movimentacoes
               (produto_id, tipo, quantidade, motivo, ticket_id, usuario, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (produto_id, tipo, quantidade, motivo_ajuste, ticket_id or None, usuario, t),
        )
    else:
        delta = quantidade if tipo == TIPO_ENTRADA else -quantidade
        db.execute(
            "UPDATE stock_produtos SET quantidade_atual=quantidade_atual+?, atualizado_em=? WHERE id=?",
            (delta, t, produto_id),
        )
        db.execute(
            """INSERT INTO stock_movimentacoes
               (produto_id, tipo, quantidade, motivo, ticket_id, usuario, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (produto_id, tipo, quantidade, motivo, ticket_id or None, usuario, t),
        )
    db.commit()


def get_movimentacoes(produto_id: int, limit: int = 50):
    return get_db().execute(
        """SELECT m.*, t.tipo as ticket_tipo, t.titulo as ticket_titulo
           FROM stock_movimentacoes m
           LEFT JOIN tickets t ON t.id = m.ticket_id
           WHERE m.produto_id = ?
           ORDER BY m.criado_em DESC LIMIT ?""",
        (produto_id, limit),
    ).fetchall()


def movimentacoes_recentes(limit: int = 20):
    return get_db().execute(
        """SELECT m.*, p.nome as produto_nome, p.unidade,
                  t.tipo as ticket_tipo, t.titulo as ticket_titulo
           FROM stock_movimentacoes m
           JOIN stock_produtos p ON p.id = m.produto_id
           LEFT JOIN tickets t ON t.id = m.ticket_id
           ORDER BY m.criado_em DESC LIMIT ?""",
        (limit,),
    ).fetchall()


# ── Vinculação com chamados ────────────────────────────────────────────

def consumos_por_ticket(ticket_id: int):
    """Retorna os itens de estoque consumidos em um chamado."""
    return get_db().execute(
        """SELECT m.*, p.nome as produto_nome, p.unidade
           FROM stock_movimentacoes m
           JOIN stock_produtos p ON p.id = m.produto_id
           WHERE m.ticket_id = ? AND m.tipo = ?
           ORDER BY m.criado_em DESC""",
        (ticket_id, TIPO_SAIDA),
    ).fetchall()


def produtos_para_select():
    return get_db().execute(
        "SELECT id, nome, unidade, quantidade_atual FROM stock_produtos WHERE ativo=1 ORDER BY nome ASC"
    ).fetchall()


# ── Dashboard ──────────────────────────────────────────────────────────

def stock_dashboard():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM stock_produtos WHERE ativo=1").fetchone()["c"]
    alertas = db.execute(
        """SELECT COUNT(*) as c FROM stock_produtos
           WHERE ativo=1 AND quantidade_minima > 0 AND quantidade_atual <= quantidade_minima"""
    ).fetchone()["c"]
    zerados = db.execute(
        "SELECT COUNT(*) as c FROM stock_produtos WHERE ativo=1 AND quantidade_atual = 0"
    ).fetchone()["c"]
    by_cat = db.execute(
        """SELECT categoria, COUNT(*) as total, SUM(quantidade_atual) as total_qtd
           FROM stock_produtos WHERE ativo=1 GROUP BY categoria ORDER BY total DESC"""
    ).fetchall()
    alertas_list = db.execute(
        """SELECT id, nome, categoria, quantidade_atual, quantidade_minima, unidade
           FROM stock_produtos
           WHERE ativo=1 AND quantidade_minima > 0 AND quantidade_atual <= quantidade_minima
           ORDER BY (quantidade_atual * 1.0 / NULLIF(quantidade_minima,0)) ASC
           LIMIT 10"""
    ).fetchall()
    return {
        "total": total,
        "alertas": alertas,
        "zerados": zerados,
        "by_cat": by_cat,
        "alertas_list": alertas_list,
    }


# ── Reversão de saídas de chamado cancelado ───────────────────────────

def reverter_saidas_chamado(ticket_id: int, usuario: str = ""):
    """Reverte todas as saídas de estoque vinculadas a um chamado cancelado."""
    db = get_db()
    saidas = db.execute(
        "SELECT produto_id, quantidade FROM stock_movimentacoes WHERE ticket_id=? AND tipo=?",
        (ticket_id, TIPO_SAIDA)
    ).fetchall()
    if not saidas:
        return 0
    t = _now()
    for s in saidas:
        db.execute(
            "UPDATE stock_produtos SET quantidade_atual=quantidade_atual+?, atualizado_em=? WHERE id=?",
            (s["quantidade"], t, s["produto_id"])
        )
        db.execute(
            """INSERT INTO stock_movimentacoes
               (produto_id, tipo, quantidade, motivo, ticket_id, usuario, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (s["produto_id"], TIPO_ENTRADA, s["quantidade"],
             f"Reversão automática — chamado #{ticket_id} cancelado", ticket_id, usuario, t)
        )
    db.commit()
    return len(saidas)
