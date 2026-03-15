from datetime import datetime
from app.db import get_db
from app.services.nf_service import TIPOS_ATIVO, TIPOS_CONSUMIVEL, TIPO_LABEL, _PREFIXO_PADRAO

TODOS_TIPOS = TIPOS_ATIVO + TIPOS_CONSUMIVEL


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_catalogo(filtros=None, apenas_ativos=True):
    filtros = filtros or {}
    db = get_db()
    q = "SELECT * FROM catalogo_produtos WHERE 1=1"
    params = []
    if apenas_ativos:
        q += " AND ativo=1"
    if filtros.get("q"):
        like = f"%{filtros['q']}%"
        q += " AND (nome LIKE ? OR codigo_oracle LIKE ?)"
        params.extend([like, like])
    if filtros.get("tipo_item"):
        q += " AND tipo_item=?"
        params.append(filtros["tipo_item"])
    q += " ORDER BY tipo_item, nome ASC"
    return db.execute(q, params).fetchall()


def get_produto_catalogo(pid: int):
    return get_db().execute(
        "SELECT * FROM catalogo_produtos WHERE id=?", (pid,)
    ).fetchone()


def criar_produto_catalogo(data: dict) -> int:
    nome = (data.get("nome") or "").strip()
    if not nome:
        raise ValueError("Nome é obrigatório.")
    tipo_item = (data.get("tipo_item") or "").strip().upper()
    if tipo_item not in TODOS_TIPOS:
        raise ValueError("Tipo inválido.")
    cod = (data.get("codigo_oracle") or "").strip()
    valor_raw = data.get("valor_unitario") or ""
    try:
        valor = float(str(valor_raw).replace(",", ".")) if valor_raw else None
    except ValueError:
        valor = None
    prefixo = (data.get("prefixo_tag") or _PREFIXO_PADRAO.get(tipo_item, "")).strip()
    unidade = (data.get("unidade") or "unidade").strip()
    t = _now()
    db = get_db()
    cur = db.execute(
        """INSERT INTO catalogo_produtos
           (nome, codigo_oracle, tipo_item, valor_unitario, prefixo_tag, unidade, ativo, criado_em, atualizado_em)
           VALUES (?,?,?,?,?,?,1,?,?)""",
        (nome, cod, tipo_item, valor, prefixo, unidade, t, t)
    )
    db.commit()
    return cur.lastrowid


def atualizar_produto_catalogo(pid: int, data: dict):
    p = get_produto_catalogo(pid)
    if not p:
        raise ValueError("Produto não encontrado.")
    nome = (data.get("nome") or "").strip()
    if not nome:
        raise ValueError("Nome é obrigatório.")
    tipo_item = (data.get("tipo_item") or "").strip().upper()
    if tipo_item not in TODOS_TIPOS:
        raise ValueError("Tipo inválido.")
    valor_raw = data.get("valor_unitario") or ""
    try:
        valor = float(str(valor_raw).replace(",", ".")) if valor_raw else None
    except ValueError:
        valor = None
    db = get_db()
    db.execute(
        """UPDATE catalogo_produtos
           SET nome=?, codigo_oracle=?, tipo_item=?, valor_unitario=?,
               prefixo_tag=?, unidade=?, ativo=?, atualizado_em=?
           WHERE id=?""",
        (
            nome,
            (data.get("codigo_oracle") or "").strip(),
            tipo_item, valor,
            (data.get("prefixo_tag") or _PREFIXO_PADRAO.get(tipo_item, "")).strip(),
            (data.get("unidade") or "unidade").strip(),
            1 if data.get("ativo") else 0,
            _now(), pid,
        )
    )
    db.commit()


def deletar_produto_catalogo(pid: int):
    get_db().execute("DELETE FROM catalogo_produtos WHERE id=?", (pid,))
    get_db().commit()
