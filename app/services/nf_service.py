"""
Serviço de Entrada por NF
--------------------------
Fluxo:
  1. Criar NF (cabeçalho)         → status RASCUNHO
  2. Adicionar itens ao rascunho  → tipo_item: ATIVO | CONSUMIVEL
  3. Preview: sistema sugere tags sequenciais editáveis
  4. Confirmar                    → cria assets / movimenta estoque → status CONFIRMADA
"""

from collections import OrderedDict
from datetime import datetime, timedelta
from app.db import get_db

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


def _clean(value):
    return (value or "").strip()


def _month_label(ym: str) -> str:
    meses = {
        "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr", "05": "Mai", "06": "Jun",
        "07": "Jul", "08": "Ago", "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
    }
    ano = ym[:4]
    mes = ym[5:7]
    return f"{meses.get(mes, mes)}/{ano}"



def _assert_asset_serial_available(serial: str, current_asset_id: int = None):
    serial = _clean(serial)
    if not serial:
        return
    db = get_db()
    row = db.execute("SELECT id, tag FROM assets WHERE UPPER(TRIM(serial_number)) = UPPER(TRIM(?))", (serial,)).fetchone()
    if row and (current_asset_id is None or row["id"] != current_asset_id):
        raise ValueError(f"Número de série já cadastrado no ativo {row['tag']}.")

def _assert_no_duplicate_serials(serials):
    seen = set()
    for serial in serials:
        norm = _clean(serial).upper()
        if not norm:
            continue
        if norm in seen:
            raise ValueError(f"Número de série duplicado na NF: {serial}")
        seen.add(norm)

# ── Prefixos automáticos por tipo ──────────────────────────────────────

_PREFIXO_PADRAO = {
    "NOTEBOOK": "NB",
    "DESKTOP":  "DK",
    "MONITOR":  "MO",
    "CELULAR":  "CEL",
    "TABLET":   "TAB",
    "OUTRO":    "AT",
}


_CAT_MAP = {
    "PERIFERICO":      "PERIFERICO",
    "CABO_ADAPTADOR":  "CABO_ADAPTADOR",
    "SIM_CARD":        "OUTRO",
    "ACESSORIO_STOCK": "PERIFERICO",
}


def _proximo_seq(tipo: str) -> int:
    """Retorna o próximo número sequencial disponível para um tipo de ativo.
    Usa MAX do sufixo numérico para ser seguro contra deleções."""
    db = get_db()
    prefixo = _PREFIXO_PADRAO.get(tipo, "AT")
    row = db.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(tag, ?) AS INTEGER)), 0) AS max_seq FROM assets WHERE tag LIKE ?",
        (len(prefixo) + 2, f"{prefixo}-%")
    ).fetchone()
    return (row["max_seq"] or 0) + 1


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
        q += " AND (n.numero_nf LIKE ? OR n.fornecedor LIKE ? OR n.base_destino LIKE ? OR n.numero_oc LIKE ?)"
        params.extend([like, like, like, like])
    q += " GROUP BY n.id ORDER BY COALESCE(n.atualizado_em, n.criado_em) DESC, n.id DESC"
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
    nf = _clean(data.get("numero_nf"))
    if not nf:
        raise ValueError("Número da NF é obrigatório.")
    db = get_db()
    now = _now()
    cur = db.execute(
        """INSERT INTO entradas_nf
           (numero_nf, numero_oc, fornecedor, base_destino, observacoes, usuario, status, criado_em, atualizado_em, cancelado_em, expira_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
        (
            nf,
            _clean(data.get("numero_oc")),
            _clean(data.get("fornecedor")),
            _clean(data.get("base_destino")),
            _clean(data.get("observacoes")),
            data.get("usuario", ""),
            STATUS_RASCUNHO,
            now,
            now,
        )
    )
    db.commit()
    return cur.lastrowid


def atualizar_entrada(entrada_id: int, data: dict, allow_confirmed: bool = False):
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")
    if e["status"] != STATUS_RASCUNHO and not (allow_confirmed and e["status"] == STATUS_CONFIRMADA):
        raise ValueError("Só é possível editar rascunhos.")

    numero_nf = _clean(data.get("numero_nf"))
    if not numero_nf:
        raise ValueError("Número da NF é obrigatório.")

    db = get_db()
    db.execute(
        """UPDATE entradas_nf
           SET numero_nf=?, numero_oc=?, fornecedor=?, base_destino=?, observacoes=?, atualizado_em=?
           WHERE id=?""",
        (
            numero_nf,
            _clean(data.get("numero_oc")),
            _clean(data.get("fornecedor")),
            _clean(data.get("base_destino")),
            _clean(data.get("observacoes")),
            _now(),
            entrada_id,
        )
    )
    db.commit()


def _nf_has_linked_tickets(entrada_id: int) -> bool:
    db = get_db()
    row = db.execute(
        """SELECT COUNT(*) AS total
           FROM tickets t
           JOIN entradas_nf_assets ena ON ena.asset_id = t.asset_id
           WHERE ena.entrada_id = ?""",
        (entrada_id,)
    ).fetchone()
    return bool(row and row["total"])


def _can_delete_confirmed(entrada_id: int):
    db = get_db()
    ativos = db.execute(
        """SELECT a.id, a.tag, a.status
           FROM entradas_nf_assets ena
           JOIN assets a ON a.id = ena.asset_id
           WHERE ena.entrada_id=?""",
        (entrada_id,)
    ).fetchall()
    for ativo in ativos:
        if ativo["status"] != "ESTOQUE":
            raise ValueError(
                f"A NF não pode ser excluída porque o ativo {ativo['tag']} não está em ESTOQUE."
            )
    if _nf_has_linked_tickets(entrada_id):
        raise ValueError("A NF não pode ser excluída porque possui ativo(s) vinculado(s) a chamado(s).")

    consumiveis = db.execute(
        """SELECT ena.stock_produto_id, i.modelo, i.quantidade, sp.quantidade_atual
           FROM entradas_nf_assets ena
           JOIN entradas_nf_itens i ON i.id = ena.item_id
           JOIN stock_produtos sp ON sp.id = ena.stock_produto_id
           WHERE ena.entrada_id=? AND ena.stock_produto_id IS NOT NULL""",
        (entrada_id,)
    ).fetchall()
    for row in consumiveis:
        if (row["quantidade_atual"] or 0) < (row["quantidade"] or 0):
            raise ValueError(
                f"A NF não pode ser excluída porque o estoque atual de '{row['modelo']}' é menor que a quantidade lançada nesta NF."
            )


def _reverter_nf_confirmada(entrada_id: int, usuario: str = "admin"):
    db = get_db()
    entrada = get_entrada(entrada_id)
    _can_delete_confirmed(entrada_id)
    now = _now()

    ativos = db.execute(
        """SELECT a.id, a.tag
           FROM entradas_nf_assets ena
           JOIN assets a ON a.id = ena.asset_id
           WHERE ena.entrada_id=?""",
        (entrada_id,)
    ).fetchall()
    for ativo in ativos:
        db.execute("DELETE FROM asset_history WHERE asset_id=?", (ativo["id"],))
        # Remove vínculo em tickets antes de deletar o asset (FK constraint)
        db.execute("UPDATE tickets SET asset_id=NULL WHERE asset_id=?", (ativo["id"],))
        # Remove vínculo em entradas_nf_assets antes de deletar o asset (FK constraint)
        db.execute("DELETE FROM entradas_nf_assets WHERE asset_id=?", (ativo["id"],))
        db.execute("DELETE FROM assets WHERE id=?", (ativo["id"],))

    consumiveis = db.execute(
        """SELECT ena.stock_produto_id, i.modelo, i.quantidade
           FROM entradas_nf_assets ena
           JOIN entradas_nf_itens i ON i.id = ena.item_id
           WHERE ena.entrada_id=? AND ena.stock_produto_id IS NOT NULL""",
        (entrada_id,)
    ).fetchall()
    for row in consumiveis:
        db.execute(
            "UPDATE stock_produtos SET quantidade_atual = quantidade_atual - ?, atualizado_em=? WHERE id=?",
            (row["quantidade"], now, row["stock_produto_id"])
        )
        db.execute(
            """INSERT INTO stock_movimentacoes
               (produto_id, tipo, quantidade, motivo, ticket_id, usuario, criado_em)
               VALUES (?, 'SAIDA', ?, ?, NULL, ?, ?)""",
            (
                row["stock_produto_id"],
                row["quantidade"],
                f"Reversão administrativa da NF {entrada['numero_nf']}",
                usuario,
                now,
            )
        )


def delete_entrada_admin(entrada_id: int, usuario: str = "admin"):
    db = get_db()
    row = db.execute("SELECT status FROM entradas_nf WHERE id=?", (entrada_id,)).fetchone()
    if not row:
        raise ValueError("NF não encontrada.")

    if row["status"] == STATUS_CONFIRMADA:
        _reverter_nf_confirmada(entrada_id, usuario=usuario)

    db.execute("DELETE FROM entradas_nf_assets WHERE entrada_id=?", (entrada_id,))
    db.execute("DELETE FROM entradas_nf_itens WHERE entrada_id=?", (entrada_id,))
    db.execute("DELETE FROM entradas_nf WHERE id=?", (entrada_id,))
    db.commit()


# ── Itens ─────────────────────────────────────────────────────────────

def adicionar_item(entrada_id: int, data: dict) -> int:
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")
    if e["status"] != STATUS_RASCUNHO:
        raise ValueError("Só é possível adicionar itens em NFs rascunho.")

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

    tipo_item = _clean(data.get("tipo_item")).upper()
    modelo = _clean(data.get("modelo"))
    if not modelo:
        raise ValueError("Modelo é obrigatório.")
    qtd = max(1, int(data.get("quantidade") or 1))

    # Para ativos: definir prefixo automático se não informado
    prefixo = _clean(data.get("prefixo_tag"))
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
            _clean(data.get("serial_numbers")),
        )
    )
    db.execute("UPDATE entradas_nf SET atualizado_em=? WHERE id=?", (_now(), entrada_id))
    db.commit()
    return cur.lastrowid


def remover_item(item_id: int, entrada_id: int):
    db = get_db()
    entrada = get_entrada(entrada_id)
    if not entrada:
        raise ValueError("Entrada não encontrada.")
    if entrada["status"] != STATUS_RASCUNHO:
        raise ValueError("Só é possível remover itens em NFs rascunho.")
    db.execute(
        "DELETE FROM entradas_nf_itens WHERE id=? AND entrada_id=?",
        (item_id, entrada_id)
    )
    db.execute("UPDATE entradas_nf SET atualizado_em=? WHERE id=?", (_now(), entrada_id))
    db.commit()


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
    Toda a operação é atômica (transação explícita).
    """
    e = get_entrada(entrada_id)
    if not e:
        raise ValueError("Entrada não encontrada.")
    if e["status"] != STATUS_RASCUNHO:
        raise ValueError("NF já confirmada ou cancelada.")

    itens = get_itens(entrada_id)
    db = get_db()
    t = _now()

    def _fget(key, default=""):
        return (form_data.get(key) or default).strip()

    created_assets = []
    created_stock  = []

    # Transação atômica — se falhar no meio, rollback total
    db.execute("BEGIN IMMEDIATE")
    try:
        for item in itens:
            tipo_item = item["tipo_item"]

            if tipo_item in TIPOS_ATIVO:
                prefixo  = item["prefixo_tag"] or _PREFIXO_PADRAO.get(tipo_item, "AT")
                seq      = _proximo_seq(tipo_item)
                seriais  = [s.strip() for s in (item["serial_numbers"] or "").split("\n") if s.strip()]

                generated_serials = []
                for i in range(item["quantidade"]):
                    key_tag    = f"tag_{item['id']}_{i}"
                    key_serial = f"serial_{item['id']}_{i}"
                    key_base   = f"base_{item['id']}_{i}"

                    tag    = _fget(key_tag)    or f"{prefixo}-{str(seq + i).zfill(3)}"
                    serial = _fget(key_serial) or (seriais[i] if i < len(seriais) else "")
                    base   = _fget(key_base)   or e["base_destino"] or ""
                    generated_serials.append(serial)

                    exists = db.execute("SELECT id FROM assets WHERE tag=?", (tag,)).fetchone()
                    if exists:
                        raise ValueError(f"Tag '{tag}' já existe. Ajuste antes de confirmar.")
                    _assert_no_duplicate_serials(generated_serials)
                    _assert_asset_serial_available(serial)

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

        db.execute(
            "UPDATE entradas_nf SET status=?, confirmado_em=?, atualizado_em=? WHERE id=?",
            (STATUS_CONFIRMADA, t, t, entrada_id)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"assets": created_assets, "stock": created_stock}


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
        "UPDATE entradas_nf SET status=?, cancelado_em=?, expira_em=?, atualizado_em=? WHERE id=?",
        (STATUS_CANCELADA, cancelado_em, expira_em, cancelado_em, entrada_id)
    )
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


def cleanup_stale_drafts(max_age_days: int = 30) -> int:
    """Cancela automaticamente rascunhos abandonados com mais de max_age_days dias."""
    db = get_db()
    now = _now()
    cutoff = (datetime.now() - timedelta(days=max(1, max_age_days))).strftime("%Y-%m-%d %H:%M:%S")
    expira = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db.execute(
        "SELECT id FROM entradas_nf WHERE status=? AND criado_em < ?",
        (STATUS_RASCUNHO, cutoff)
    ).fetchall()
    for row in rows:
        db.execute(
            "UPDATE entradas_nf SET status=?, cancelado_em=?, expira_em=?, atualizado_em=? WHERE id=?",
            (STATUS_CANCELADA, now, expira, now, row["id"])
        )
    db.commit()
    return len(rows)


# ── Dashboard NF ──────────────────────────────────────────────────────

def nf_dashboard_stats(filtros=None):
    filtros = filtros or {}
    db = get_db()
    where = ["(expira_em IS NULL OR expira_em > ?)"]
    params = [_now()]

    localizacao = _clean(filtros.get("localizacao"))
    if localizacao:
        where.append("COALESCE(base_destino, '') = ?")
        params.append(localizacao)

    base_where = " AND ".join(where)

    total_nf = db.execute(f"SELECT COUNT(*) AS total FROM entradas_nf WHERE {base_where}", params).fetchone()["total"]
    status_rows = db.execute(
        f"SELECT status, COUNT(*) AS total FROM entradas_nf WHERE {base_where} GROUP BY status ORDER BY status",
        params,
    ).fetchall()
    by_status = OrderedDict((r["status"], r["total"]) for r in status_rows)

    month_rows = db.execute(
        f"""SELECT substr(criado_em, 1, 7) AS ym, COUNT(*) AS total
             FROM entradas_nf
             WHERE {base_where}
             GROUP BY substr(criado_em, 1, 7)
             ORDER BY ym DESC
             LIMIT 12""",
        params,
    ).fetchall()
    month_rows = list(reversed(month_rows))
    months = [{"key": r["ym"], "label": _month_label(r["ym"]), "total": r["total"]} for r in month_rows]

    local_rows = db.execute(
        f"""SELECT COALESCE(NULLIF(base_destino, ''), 'Sem localização') AS localizacao,
                    COUNT(*) AS total
             FROM entradas_nf
             WHERE {base_where}
             GROUP BY COALESCE(NULLIF(base_destino, ''), 'Sem localização')
             ORDER BY total DESC, localizacao ASC
             LIMIT 10""",
        params,
    ).fetchall()
    by_location = [{"label": r["localizacao"], "total": r["total"]} for r in local_rows]

    asset_type_rows = db.execute(
        f"""SELECT i.tipo_item, SUM(i.quantidade) AS total
             FROM entradas_nf n
             JOIN entradas_nf_itens i ON i.entrada_id = n.id
             WHERE {base_where}
             GROUP BY i.tipo_item
             ORDER BY total DESC""",
        params,
    ).fetchall()
    asset_mix = [{"label": TIPO_LABEL.get(r["tipo_item"], r["tipo_item"]), "total": r["total"] or 0} for r in asset_type_rows]

    totals = db.execute(
        f"""SELECT
                COALESCE(SUM(CASE WHEN i.tipo_item IN ({','.join('?'*len(TIPOS_ATIVO))}) THEN i.quantidade ELSE 0 END), 0) AS total_ativos,
                COALESCE(SUM(CASE WHEN i.tipo_item IN ({','.join('?'*len(TIPOS_CONSUMIVEL))}) THEN i.quantidade ELSE 0 END), 0) AS total_consumiveis
             FROM entradas_nf n
             LEFT JOIN entradas_nf_itens i ON i.entrada_id = n.id
             WHERE {base_where}""",
        [*TIPOS_ATIVO, *TIPOS_CONSUMIVEL, *params],
    ).fetchone()

    locations = db.execute(
        """SELECT DISTINCT COALESCE(NULLIF(base_destino, ''), 'Sem localização') AS localizacao
           FROM entradas_nf
           WHERE expira_em IS NULL OR expira_em > ?
           ORDER BY localizacao ASC""",
        (_now(),),
    ).fetchall()

    return {
        "total_nf": total_nf,
        "total_ativos": totals["total_ativos"] if totals else 0,
        "total_consumiveis": totals["total_consumiveis"] if totals else 0,
        "by_status": by_status,
        "months": months,
        "by_location": by_location,
        "asset_mix": asset_mix,
        "locations": [r["localizacao"] for r in locations],
        "selected_location": localizacao,
    }



def nf_dashboard_month_detail(month: str, localizacao: str = ""):
    if not month or len(month) != 7:
        return []
    db = get_db()
    where = ["substr(n.criado_em, 1, 7) = ?", "(n.expira_em IS NULL OR n.expira_em > ?)"]
    params = [month, _now()]
    localizacao = _clean(localizacao)
    if localizacao:
        where.append("COALESCE(n.base_destino, '') = ?")
        params.append(localizacao)
    q = f"""
        SELECT n.id, n.numero_nf, n.numero_oc, n.fornecedor, n.base_destino, n.criado_em, n.status,
               COUNT(i.id) AS total_itens,
               COALESCE(SUM(i.quantidade), 0) AS total_unidades
        FROM entradas_nf n
        LEFT JOIN entradas_nf_itens i ON i.entrada_id = n.id
        WHERE {' AND '.join(where)}
        GROUP BY n.id
        ORDER BY n.criado_em DESC, n.id DESC
    """
    return db.execute(q, params).fetchall()
