"""
Serviço de Entrada por NF
--------------------------
Fluxo:
  1. Criar NF (cabeçalho)         → status RASCUNHO
  2. Adicionar itens ao rascunho  → tipo_item: ATIVO | CONSUMIVEL
  3. Preview: sistema sugere tags sequenciais editáveis
  4. Confirmar                    → cria assets / movimenta estoque → status CONFIRMADA
"""

from datetime import datetime, timedelta
from app.db import get_db
from app.services.asset_service import ASSET_TYPES, log_asset_event

# Tipos que geram ativo individual (rastreado por tag)
TIPOS_ATIVO = ["NOTEBOOK", "DESKTOP", "MONITOR", "CELULAR", "TABLET", "OUTRO"]
# Tipos que vão para estoque (quantidade)
TIPOS_CONSUMIVEL = ["PERIFERICO", "CABO_ADAPTADOR", "SIM_CARD", "ACESSORIO_STOCK"]

TIPO_LABEL = {
    "NOTEBOOK":        "Notebook",
    "DESKTOP":         "Desktop",
    "MONITOR":         "Monitor",
    "CELULAR":         "Celular",
    "TABLET":          "Tablet",
    "OUTRO":           "Outro (ativo)",
    "PERIFERICO":      "Periférico (estoque)",
    "CABO_ADAPTADOR":  "Cabo / Adaptador (estoque)",
    "SIM_CARD":        "SIM Card (estoque)",
    "ACESSORIO_STOCK": "Acessório (estoque)",
}

STATUS_RASCUNHO   = "RASCUNHO"
STATUS_CONFIRMADA = "CONFIRMADA"
STATUS_CANCELADA  = "CANCELADA"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Prefixos automáticos por tipo ──────────────────────────────────────

_PREFIXO_PADRAO = {
    "NOTEBOOK": "NB",
    "DESKTOP":  "DK",
    "MONITOR":  "MO",
    "CELULAR":  "CEL",
    "TABLET":   "TAB",
    "OUTRO":    "AT",
}


def _proximo_seq(tipo: str) -> int:
    """Retorna o próximo número sequencial disponível para um tipo de ativo."""
    db = get_db()
    prefixo = _PREFIXO_PADRAO.get(tipo, "AT")
    row = db.execute(
        "SELECT COUNT(*) as c FROM assets WHERE tag LIKE ?",
        (f"{prefixo}-%",)
    ).fetchone()
    return (row["c"] if row else 0) + 1


def _gerar_tags(tipo: str, prefixo: str, quantidade: int, start_seq: int) -> list:
    tags = []
    for i in range(quantidade):
        tags.append(f"{prefixo}-{str(start_seq + i).zfill(3)}")
    return tags


# ── CRUD da NF ────────────────────────────────────────────────────────

def list_entradas(filtros=None):
    filtros = filtros or {}
    db = get_db()
    q = """
        SELECT n.*,
               COUNT(i.id) as total_itens,
               SUM(i.quantidade) as total_unidades
        FROM entradas_nf n
        LEFT JOIN entradas_nf_itens i ON i.entrada_id = n.id
        WHERE 1=1
          AND (n.expira_em IS NULL OR n.expira_em > ?)
    """
    params = [_now()]
    if filtros.get("status"):
        q += " AND n.status = ?"
        params.append(filtros["status"])
    if filtros.get("q"):
        like = f"%{filtros['q']}%"
        q += " AND (n.numero_nf LIKE ? OR n.fornecedor LIKE ? OR n.base_destino LIKE ?)"
        params.extend([like, like, like])
    q += " GROUP BY n.id ORDER BY n.criado_em DESC"
    return db.execute(q, params).fetchall()


def get_entrada(entrada_id: int):
    return get_db().execute(
        "SELECT * FROM entradas_nf WHERE id = ? AND (expira_em IS NULL OR expira_em > ?)", (entrada_id, _now())
    ).fetchone()


def get_itens(entrada_id: int):
    return get_db().execute(
        "SELECT * FROM entradas_nf_itens WHERE entrada_id = ? ORDER BY id",
        (entrada_id,)
    ).fetchall()


def get_assets_gerados(entrada_id: int):
    return get_db().execute(
        """SELECT na.*, a.tag, a.modelo, a.tipo, a.status as asset_status,
                  a.serial_number, a.local_base
           FROM entradas_nf_assets na
           LEFT JOIN assets a ON a.id = na.asset_id
           WHERE na.entrada_id = ?
           ORDER BY na.id""",
        (entrada_id,)
    ).fetchall()


def criar_entrada(data: dict) -> int:
    nf = (data.get("numero_nf") or "").strip()
    if not nf:
        raise ValueError("Número da NF é obrigatório.")
    db = get_db()
    cur = db.execute(
        """INSERT INTO entradas_nf
           (numero_nf, numero_oc, fornecedor, base_destino, observacoes, usuario, status, criado_em, cancelado_em, expira_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
        (
            nf,
            (data.get("numero_oc") or "").strip(),
            (data.get("fornecedor") or "").strip(),
            (data.get("base_destino") or "").strip(),
            (data.get("observacoes") or "").strip(),
            data.get("usuario", ""),
            STATUS_RASCUNHO,
            _now(),
        )
    )
    db.commit()
    return cur.lastrowid


def atualizar_entrada(entrada_id: int, data: dict):
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")
    if e["status"] != STATUS_RASCUNHO:
        raise ValueError("Só é possível editar rascunhos.")
    db = get_db()
    db.execute(
        """UPDATE entradas_nf
           SET numero_nf=?, numero_oc=?, fornecedor=?, base_destino=?, observacoes=?
           WHERE id=?""",
        (
            (data.get("numero_nf") or "").strip(),
            (data.get("numero_oc") or "").strip(),
            (data.get("fornecedor") or "").strip(),
            (data.get("base_destino") or "").strip(),
            (data.get("observacoes") or "").strip(),
            entrada_id,
        )
    )
    db.commit()


# ── Itens ─────────────────────────────────────────────────────────────

def adicionar_item(entrada_id: int, data: dict) -> int:
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")

    # Se vier do catálogo, preenche campos automaticamente
    catalogo_id = data.get("catalogo_id")
    if catalogo_id:
        from app.services.catalogo_service import get_produto_catalogo
        cat = get_produto_catalogo(int(catalogo_id))
        if cat:
            data = dict(data)
            data.setdefault("tipo_item", cat["tipo_item"])
            data.setdefault("modelo",    cat["nome"])
            if cat["prefixo_tag"]:
                data.setdefault("prefixo_tag", cat["prefixo_tag"])

    tipo_item = (data.get("tipo_item") or "").strip().upper()
    modelo = (data.get("modelo") or "").strip()
    if not modelo:
        raise ValueError("Modelo é obrigatório.")
    qtd = max(1, int(data.get("quantidade") or 1))

    # Para ativos: definir prefixo automático se não informado
    prefixo = (data.get("prefixo_tag") or "").strip()
    if tipo_item in TIPOS_ATIVO and not prefixo:
        prefixo = _PREFIXO_PADRAO.get(tipo_item, "AT")

    db = get_db()
    cur = db.execute(
        """INSERT INTO entradas_nf_itens
           (entrada_id, tipo_item, tipo, modelo, quantidade, prefixo_tag, serial_numbers, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDENTE')""",
        (
            entrada_id,
            tipo_item,
            tipo_item if tipo_item in TIPOS_ATIVO else None,
            modelo,
            qtd,
            prefixo,
            (data.get("serial_numbers") or "").strip(),
        )
    )
    db.commit()
    return cur.lastrowid


def remover_item(item_id: int, entrada_id: int):
    get_db().execute(
        "DELETE FROM entradas_nf_itens WHERE id=? AND entrada_id=?",
        (item_id, entrada_id)
    )
    get_db().commit()


# ── Preview ───────────────────────────────────────────────────────────

def gerar_preview(entrada_id: int) -> list:
    """
    Retorna lista de dicts com o que será criado ao confirmar.
    Para ativos: uma linha por unidade com tag sugerida.
    Para consumíveis: uma linha por item com quantidade.
    """
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")

    itens = get_itens(entrada_id)
    preview = []

    for item in itens:
        tipo_item = item["tipo_item"]

        if tipo_item in TIPOS_ATIVO:
            prefixo = item["prefixo_tag"] or _PREFIXO_PADRAO.get(tipo_item, "AT")
            seq = _proximo_seq(tipo_item)
            # Seriais informados (um por linha)
            seriais = [s.strip() for s in (item["serial_numbers"] or "").split("\n") if s.strip()]

            for i in range(item["quantidade"]):
                tag_sugerida = f"{prefixo}-{str(seq + i).zfill(3)}"
                preview.append({
                    "item_id":    item["id"],
                    "tipo_item":  tipo_item,
                    "modelo":     item["modelo"],
                    "tag":        tag_sugerida,
                    "serial":     seriais[i] if i < len(seriais) else "",
                    "local_base": e["base_destino"] or "",
                    "idx":        i,
                    "is_ativo":   True,
                })
        else:
            preview.append({
                "item_id":   item["id"],
                "tipo_item": tipo_item,
                "modelo":    item["modelo"],
                "quantidade": item["quantidade"],
                "is_ativo":  False,
            })

    return preview


# ── Confirmação ────────────────────────────────────────────────────────

def confirmar_entrada(entrada_id: int, form_data: dict, usuario: str):
    """
    Processa o preview confirmado:
    - Cria assets individuais para cada linha de ativo
    - Registra entrada de estoque para consumíveis
    - Marca NF como CONFIRMADA
    """
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")
    if e["status"] != STATUS_RASCUNHO:
        raise ValueError("NF já confirmada ou cancelada.")

    itens = get_itens(entrada_id)
    db = get_db()
    t = _now()

    # Mapear seriais e tags vindos do form (prefixo: nf_{entrada_id}_item_{item_id}_idx_{i}_tag)
    def _fget(key, default=""):
        return (form_data.get(key) or default).strip()

    created_assets = []
    created_stock  = []

    for item in itens:
        tipo_item = item["tipo_item"]

        if tipo_item in TIPOS_ATIVO:
            prefixo  = item["prefixo_tag"] or _PREFIXO_PADRAO.get(tipo_item, "AT")
            seq      = _proximo_seq(tipo_item)
            seriais  = [s.strip() for s in (item["serial_numbers"] or "").split("\n") if s.strip()]

            for i in range(item["quantidade"]):
                key_tag    = f"tag_{item['id']}_{i}"
                key_serial = f"serial_{item['id']}_{i}"
                key_base   = f"base_{item['id']}_{i}"

                tag    = _fget(key_tag)    or f"{prefixo}-{str(seq + i).zfill(3)}"
                serial = _fget(key_serial) or (seriais[i] if i < len(seriais) else "")
                base   = _fget(key_base)   or e["base_destino"] or ""

                # Verificar tag duplicada
                exists = db.execute("SELECT id FROM assets WHERE tag=?", (tag,)).fetchone()
                if exists:
                    raise ValueError(f"Tag '{tag}' já existe. Ajuste antes de confirmar.")

                # Mapear tipo_item → ASSET_TYPE
                tipo_asset = tipo_item if tipo_item in TIPOS_ATIVO else "OUTRO"
                if tipo_asset not in ["NOTEBOOK","DESKTOP","MONITOR","CELULAR","OUTRO"]:
                    tipo_asset = "OUTRO"

                cur = db.execute(
                    """INSERT INTO assets
                       (tag, tipo, modelo, serial_number, local_base, responsavel, status, observacoes, criado_em, atualizado_em)
                       VALUES (?, ?, ?, ?, ?, '', 'ESTOQUE', ?, ?, ?)""",
                    (tag, tipo_asset, item["modelo"], serial, base,
                     f"Entrada NF {e['numero_nf']}", t, t)
                )
                asset_id = cur.lastrowid

                db.execute(
                    """INSERT INTO asset_history (asset_id, evento, detalhe, criado_em)
                       VALUES (?, 'ENTRADA_NF', ?, ?)""",
                    (asset_id, f"NF {e['numero_nf']} | OC {e['numero_oc'] or '-'} | {e['fornecedor'] or '-'}", t)
                )

                db.execute(
                    """INSERT INTO entradas_nf_assets (entrada_id, item_id, asset_id, tag, serial_number)
                       VALUES (?, ?, ?, ?, ?)""",
                    (entrada_id, item["id"], asset_id, tag, serial)
                )
                created_assets.append(tag)

        else:
            # Consumível → movimentar estoque existente ou criar produto
            # Procura produto pelo nome exato
            prod = db.execute(
                "SELECT id, quantidade_atual FROM stock_produtos WHERE nome=? AND ativo=1",
                (item["modelo"],)
            ).fetchone()

            qtd = item["quantidade"]

            if prod:
                db.execute(
                    "UPDATE stock_produtos SET quantidade_atual=quantidade_atual+?, atualizado_em=? WHERE id=?",
                    (qtd, t, prod["id"])
                )
                prod_id = prod["id"]
            else:
                cur = db.execute(
                    """INSERT INTO stock_produtos
                       (nome, categoria, unidade, localizacao, quantidade_atual, quantidade_minima, ativo, criado_em, atualizado_em)
                       VALUES (?, ?, 'unidade', ?, ?, 0, 1, ?, ?)""",
                    (item["modelo"],
                     _CAT_MAP.get(tipo_item, "OUTRO"),
                     e["base_destino"] or "",
                     qtd, t, t)
                )
                prod_id = cur.lastrowid

            db.execute(
                """INSERT INTO stock_movimentacoes
                   (produto_id, tipo, quantidade, motivo, ticket_id, usuario, criado_em)
                   VALUES (?, 'ENTRADA', ?, ?, NULL, ?, ?)""",
                (prod_id, qtd, f"NF {e['numero_nf']} | {e['fornecedor'] or ''}", usuario, t)
            )
            db.execute(
                """INSERT INTO entradas_nf_assets (entrada_id, item_id, stock_produto_id)
                   VALUES (?, ?, ?)""",
                (entrada_id, item["id"], prod_id)
            )
            created_stock.append(item["modelo"])

    # Marcar NF como confirmada
    db.execute(
        "UPDATE entradas_nf SET status=?, confirmado_em=? WHERE id=?",
        (STATUS_CONFIRMADA, t, entrada_id)
    )
    db.commit()

    return {"assets": created_assets, "stock": created_stock}


_CAT_MAP = {
    "PERIFERICO":      "PERIFERICO",
    "CABO_ADAPTADOR":  "CABO_ADAPTADOR",
    "SIM_CARD":        "OUTRO",
    "ACESSORIO_STOCK": "PERIFERICO",
}


def cancelar_entrada(entrada_id: int, retention_days: int = 15):
    db = get_db()
    row = db.execute("SELECT status FROM entradas_nf WHERE id=?", (entrada_id,)).fetchone()
    if not row:
        raise ValueError("NF não encontrada.")
    if row["status"] != STATUS_RASCUNHO:
        raise ValueError("Apenas NFs em rascunho podem ser canceladas.")
    cancelado_em = _now()
    expira_em = (datetime.now() + timedelta(days=max(1, int(retention_days or 15)))).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE entradas_nf SET status=?, cancelado_em=?, expira_em=? WHERE id=?",
        (STATUS_CANCELADA, cancelado_em, expira_em, entrada_id)
    )
    db.commit()


def delete_entrada_admin(entrada_id: int):
    db = get_db()
    row = db.execute("SELECT status FROM entradas_nf WHERE id=?", (entrada_id,)).fetchone()
    if not row:
        raise ValueError("NF não encontrada.")
    if row["status"] == STATUS_CONFIRMADA:
        raise ValueError("NFs confirmadas não podem ser excluídas por segurança.")
    db.execute("DELETE FROM entradas_nf_assets WHERE entrada_id=?", (entrada_id,))
    db.execute("DELETE FROM entradas_nf_itens WHERE entrada_id=?", (entrada_id,))
    db.execute("DELETE FROM entradas_nf WHERE id=?", (entrada_id,))
    db.commit()


def cleanup_expired_cancelled_drafts(now: str | None = None) -> int:
    db = get_db()
    now = now or _now()
    rows = db.execute(
        "SELECT id FROM entradas_nf WHERE status=? AND expira_em IS NOT NULL AND expira_em <= ?",
        (STATUS_CANCELADA, now)
    ).fetchall()
    for row in rows:
        db.execute("DELETE FROM entradas_nf_assets WHERE entrada_id=?", (row["id"],))
        db.execute("DELETE FROM entradas_nf_itens WHERE entrada_id=?", (row["id"],))
        db.execute("DELETE FROM entradas_nf WHERE id=?", (row["id"],))
    db.commit()
    return len(rows)
