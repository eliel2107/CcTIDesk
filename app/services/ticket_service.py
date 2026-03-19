"""
Serviço de Chamados — CRUD, status, etapas, anexos, atribuição.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from app.db import get_db
from app.helpers import (
    _now, _today_ymd, _clean, _parse_float, _validate_date_ymd, _parse_dt,
    validate_choice,
)
from app.constants import (
    STATUSES, CLASSIFICATIONS, TYPES, PRIORITIES,
    QUEUE_VISIBLE_STATUSES, LOCKED_STATUSES, SUGGESTED_STEPS, TRANSICOES_VALIDAS,
)


# ── Logging / Histórico ─────────────────────────────────────────────────

def log_event(ticket_id: int, evento: str, detalhe: str = ""):
    db = get_db()
    db.execute(
        "INSERT INTO ticket_log (ticket_id, evento, detalhe, criado_em) VALUES (?, ?, ?, ?)",
        (ticket_id, evento, detalhe, _now())
    )
    db.commit()


def _log_asset_history(asset_id: Optional[int], evento: str, detalhe: str = ""):
    if not asset_id:
        return
    db = get_db()
    db.execute(
        "INSERT INTO asset_history (asset_id, evento, detalhe, criado_em) VALUES (?, ?, ?, ?)",
        (asset_id, evento, detalhe, _now())
    )
    db.commit()


# ── Numeração ────────────────────────────────────────────────────────────

def _next_numero(db, classificacao: str) -> str:
    # Lê o maior número existente sem BEGIN IMMEDIATE explícito.
    # O commit é responsabilidade do chamador (create_ticket), que já envolve
    # o INSERT completo em uma transação. Evita transação aninhada que pode
    # causar bloqueio em SQLite com WAL mode.
    prefix = "REQ" if classificacao == "REQUISICAO" else "INC"
    row = db.execute(
        """SELECT COALESCE(
               MAX(CAST(SUBSTR(numero_chamado, ?) AS INTEGER)), 0
           ) as max_seq
           FROM tickets
           WHERE classificacao = ?
             AND numero_chamado LIKE ?""",
        (len(prefix) + 2, classificacao, f"{prefix}-%")
    ).fetchone()
    seq = (row["max_seq"] or 0) + 1
    return f"{prefix}-{seq:04d}"


# ── Prioridade padrão da categoria ──────────────────────────────────────

def _category_default_priority(categoria_id: Optional[int]) -> Optional[str]:
    if not categoria_id:
        return None
    row = get_db().execute("SELECT prioridade_padrao FROM categories WHERE id=?", (categoria_id,)).fetchone()
    if not row:
        return None
    value = _clean(row["prioridade_padrao"]).upper()
    return value if value in PRIORITIES else None


# ── Etapas (Checklist) ──────────────────────────────────────────────────

def _insert_steps(ticket_id: int, tipo: str):
    steps = SUGGESTED_STEPS.get(tipo, [])
    db = get_db()
    for i, st in enumerate(steps, start=1):
        db.execute(
            "INSERT INTO ticket_steps (ticket_id, step_order, step_text, done, done_em) VALUES (?, ?, ?, 0, NULL)",
            (ticket_id, i, st)
        )
    db.commit()


def normalize_steps(ticket_id: int):
    db = get_db()
    rows = db.execute("SELECT id FROM ticket_steps WHERE ticket_id=? ORDER BY step_order ASC, id ASC", (ticket_id,)).fetchall()
    for i, r in enumerate(rows, start=1):
        db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (i, r["id"]))
    db.commit()


def list_steps(ticket_id: int):
    return get_db().execute(
        "SELECT id, step_order, step_text, done, done_em FROM ticket_steps WHERE ticket_id=? ORDER BY step_order ASC, id ASC",
        (ticket_id,)
    ).fetchall()


def toggle_step(step_id: int, done: bool):
    db = get_db()
    row = db.execute("SELECT ticket_id FROM ticket_steps WHERE id=?", (step_id,)).fetchone()
    if not row:
        raise ValueError("Etapa não encontrada.")
    ticket_id = row["ticket_id"]
    db.execute(
        "UPDATE ticket_steps SET done=?, done_em=? WHERE id=?",
        (1 if done else 0, _now() if done else None, step_id)
    )
    db.execute("UPDATE tickets SET atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    log_event(ticket_id, "ETAPA", f"Etapa {'concluída' if done else 'reaberta'} (id={step_id}).")


def add_step(ticket_id: int, text: str, position: str = "end", ref_step_id: Optional[int] = None):
    text = _clean(text)
    if not text:
        raise ValueError("Texto da etapa é obrigatório.")
    db = get_db()
    steps = list_steps(ticket_id)
    if position == "end" or not steps:
        order = len(steps) + 1
        db.execute("INSERT INTO ticket_steps (ticket_id, step_order, step_text, done, done_em) VALUES (?, ?, ?, 0, NULL)",
                   (ticket_id, order, text))
    elif position == "before" and ref_step_id:
        ref = db.execute("SELECT step_order FROM ticket_steps WHERE id=? AND ticket_id=?", (ref_step_id, ticket_id)).fetchone()
        if not ref:
            raise ValueError("Etapa referência inválida.")
        ref_order = ref["step_order"]
        db.execute("UPDATE ticket_steps SET step_order = step_order + 1 WHERE ticket_id=? AND step_order >= ?",
                   (ticket_id, ref_order))
        db.execute("INSERT INTO ticket_steps (ticket_id, step_order, step_text, done, done_em) VALUES (?, ?, ?, 0, NULL)",
                   (ticket_id, ref_order, text))
    else:
        order = len(steps) + 1
        db.execute("INSERT INTO ticket_steps (ticket_id, step_order, step_text, done, done_em) VALUES (?, ?, ?, 0, NULL)",
                   (ticket_id, order, text))
    db.execute("UPDATE tickets SET atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    normalize_steps(ticket_id)
    log_event(ticket_id, "CHECKLIST", f"Etapa adicionada: {text}")


def delete_step(ticket_id: int, step_id: int):
    db = get_db()
    row = db.execute("SELECT step_text FROM ticket_steps WHERE id=? AND ticket_id=?", (step_id, ticket_id)).fetchone()
    if not row:
        raise ValueError("Etapa não encontrada.")
    db.execute("DELETE FROM ticket_steps WHERE id=? AND ticket_id=?", (step_id, ticket_id))
    db.execute("UPDATE tickets SET atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    normalize_steps(ticket_id)
    log_event(ticket_id, "CHECKLIST", f"Etapa removida: {row['step_text']}")


def move_step(ticket_id: int, step_id: int, direction: str):
    db = get_db()
    row = db.execute("SELECT id, step_order FROM ticket_steps WHERE id=? AND ticket_id=?", (step_id, ticket_id)).fetchone()
    if not row:
        raise ValueError("Etapa não encontrada.")
    order = row["step_order"]
    if direction == "up" and order > 1:
        other = db.execute("SELECT id FROM ticket_steps WHERE ticket_id=? AND step_order=?", (ticket_id, order - 1)).fetchone()
        if other:
            db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order - 1, step_id))
            db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order, other["id"]))
    elif direction == "down":
        maxo = db.execute("SELECT MAX(step_order) as m FROM ticket_steps WHERE ticket_id=?", (ticket_id,)).fetchone()["m"] or 1
        if order < maxo:
            other = db.execute("SELECT id FROM ticket_steps WHERE ticket_id=? AND step_order=?", (ticket_id, order + 1)).fetchone()
            if other:
                db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order + 1, step_id))
                db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order, other["id"]))
    db.execute("UPDATE tickets SET atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    normalize_steps(ticket_id)


# ── Anexos ───────────────────────────────────────────────────────────────

def list_attachments(ticket_id: int):
    return get_db().execute(
        "SELECT id, original_name, stored_name, mime_type, size_bytes, uploaded_em FROM attachments WHERE ticket_id=? ORDER BY uploaded_em DESC",
        (ticket_id,)
    ).fetchall()


def get_attachment(ticket_id: int, attachment_id: int):
    return get_db().execute(
        "SELECT id, original_name, stored_name FROM attachments WHERE id=? AND ticket_id=?",
        (attachment_id, ticket_id)
    ).fetchone()


def count_attachments(ticket_id: int) -> int:
    return get_db().execute(
        "SELECT COUNT(*) as c FROM attachments WHERE ticket_id=?", (ticket_id,)
    ).fetchone()["c"]


def add_attachment(ticket_id: int, stored_name: str, original_name: str, mime_type: str, size_bytes: int):
    db = get_db()
    db.execute(
        "INSERT INTO attachments (ticket_id, stored_name, original_name, mime_type, size_bytes, uploaded_em) VALUES (?, ?, ?, ?, ?, ?)",
        (ticket_id, stored_name, original_name, mime_type, size_bytes, _now())
    )
    db.commit()
    log_event(ticket_id, "ANEXO", f"Arquivo anexado: {original_name}")


def delete_attachment(ticket_id: int, attachment_id: int) -> str:
    db = get_db()
    row = get_attachment(ticket_id, attachment_id)
    if not row:
        raise ValueError("Anexo não encontrado.")
    db.execute("DELETE FROM attachments WHERE id=? AND ticket_id=?", (attachment_id, ticket_id))
    db.execute("UPDATE tickets SET atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    log_event(ticket_id, "ANEXO_REMOVIDO", row["original_name"])
    return row["stored_name"]


# ── CRUD de Chamados ─────────────────────────────────────────────────────

def create_ticket(data: Dict[str, Any]) -> int:
    from app.services.sla_service import calc_sla_deadline

    tipo = data.get("tipo") or "GERAL"
    classificacao = data.get("classificacao", "REQUISICAO")
    if classificacao not in CLASSIFICATIONS:
        classificacao = "REQUISICAO"

    categoria_id = (int(data.get("categoria_id")) if str(data.get("categoria_id", "")).strip().isdigit() else None)
    prioridade_informada = _clean(data.get("prioridade")).upper()
    prioridade = _category_default_priority(categoria_id) or prioridade_informada or "MEDIA"
    prioridade = validate_choice(prioridade, PRIORITIES, "Prioridade")
    titulo = _clean(data.get("titulo"))
    if not titulo:
        raise ValueError("Título é obrigatório.")
    if len(titulo) > 300:
        raise ValueError("Título muito longo (máximo 300 caracteres).")

    t = _now()
    sla_deadline = calc_sla_deadline(categoria_id, t) if categoria_id else None

    status = "ABERTO"
    if categoria_id:
        db_pre = get_db()
        cat = db_pre.execute("SELECT requer_aprovacao, valor_aprovacao_limite FROM categories WHERE id=?", (categoria_id,)).fetchone()
        if cat and cat["requer_aprovacao"]:
            valor = _parse_float(data.get("valor_estimado"))
            limite = _parse_float(cat["valor_aprovacao_limite"])
            # Requer aprovação se:
            # - Não há limite configurado (categoria sempre exige aprovação), OU
            # - Não há valor estimado informado (não dá para validar se está abaixo do limite), OU
            # - Valor estimado atinge/supera o limite.
            if not limite or valor is None or valor >= limite:
                status = "AGUARDANDO_APROVACAO"

    payload = dict(
        tipo=tipo, classificacao=classificacao,
        titulo=titulo, descricao=_clean(data.get("descricao")), solicitante=_clean(data.get("solicitante")),
        prioridade=prioridade, status=status,
        responsavel=_clean(data.get("responsavel")), fornecedor=_clean(data.get("fornecedor")),
        centro_custo=_clean(data.get("centro_custo")), valor_estimado=_parse_float(data.get("valor_estimado")),
        link_pedido=_clean(data.get("link_pedido")), codigo_rastreio=_clean(data.get("codigo_rastreio")),
        data_limite=_validate_date_ymd(data.get("data_limite")),
        destinatario=_clean(data.get("destinatario")), telefone=_clean(data.get("telefone")), endereco=_clean(data.get("endereco")),
        cidade=_clean(data.get("cidade")), estado=_clean(data.get("estado")), cep=_clean(data.get("cep")),
        asset_id=(int(data.get("asset_id")) if str(data.get("asset_id", "")).strip().isdigit() else None),
        categoria_id=categoria_id,
        requester_user_id=(int(data.get("requester_user_id")) if str(data.get("requester_user_id", "")).strip().isdigit() else None),
        assigned_user_id=(int(data.get("assigned_user_id")) if str(data.get("assigned_user_id", "")).strip().isdigit() else None),
        sla_deadline=sla_deadline, closed_em=None, criado_em=t, atualizado_em=t,
    )

    db = get_db()
    numero = _next_numero(db, classificacao)
    cur = db.execute("""INSERT INTO tickets (
        tipo, classificacao, numero_chamado, titulo, descricao, solicitante, prioridade, status,
        responsavel, fornecedor, centro_custo, valor_estimado, link_pedido, codigo_rastreio, data_limite,
        destinatario, telefone, endereco, cidade, estado, cep, asset_id, categoria_id,
        requester_user_id, assigned_user_id, sla_deadline, closed_em, criado_em, atualizado_em
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        payload["tipo"], payload["classificacao"], numero, payload["titulo"], payload["descricao"],
        payload["solicitante"], payload["prioridade"], payload["status"],
        payload["responsavel"], payload["fornecedor"], payload["centro_custo"], payload["valor_estimado"],
        payload["link_pedido"], payload["codigo_rastreio"], payload["data_limite"],
        payload["destinatario"], payload["telefone"], payload["endereco"], payload["cidade"],
        payload["estado"], payload["cep"], payload["asset_id"], payload["categoria_id"],
        payload["requester_user_id"], payload["assigned_user_id"], payload["sla_deadline"],
        payload["closed_em"], payload["criado_em"], payload["atualizado_em"]
    ))
    db.commit()
    ticket_id = cur.lastrowid
    log_event(ticket_id, "CRIADO", f"Chamado {numero} criado como {status}")
    if categoria_id and _category_default_priority(categoria_id):
        log_event(ticket_id, "PRIORIDADE_AUTOMATICA", f"Prioridade definida automaticamente pela categoria: {prioridade}.")
    if payload["asset_id"]:
        _log_asset_history(payload["asset_id"], "VINCULADO_CHAMADO", f"Chamado {numero} criado e vinculado ao ativo.")

    if not payload["assigned_user_id"] and categoria_id and status == "ABERTO":
        log_event(ticket_id, "AGUARDANDO_ASSUNCAO", "Chamado entrou na fila da categoria aguardando aceite manual.")

    # Checklist padrão da categoria
    if categoria_id:
        import json as _json
        cat_row = db.execute("SELECT checklist_padrao FROM categories WHERE id=?", (categoria_id,)).fetchone()
        if cat_row and cat_row["checklist_padrao"]:
            try:
                steps = _json.loads(cat_row["checklist_padrao"])
                for i, step_text in enumerate(steps, 1):
                    if step_text.strip():
                        db.execute("INSERT INTO ticket_steps (ticket_id,step_order,step_text,done) VALUES (?,?,?,0)",
                                   (ticket_id, i, step_text.strip()))
                db.commit()
                return ticket_id
            except Exception:
                pass
    _insert_steps(ticket_id, tipo)
    return ticket_id


def get_ticket(ticket_id: int):
    return get_db().execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def get_logs(ticket_id: int):
    return get_db().execute(
        "SELECT criado_em, evento, detalhe FROM ticket_log WHERE ticket_id=? ORDER BY criado_em ASC",
        (ticket_id,)
    ).fetchall()


def list_tickets(filters: Dict[str, Any]):
    db = get_db()
    q = """SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, asset_id, atualizado_em
           FROM tickets WHERE 1=1"""
    params = []
    status = _clean(filters.get("status"))
    if status:
        status = validate_choice(status, STATUSES, "Status")
        q += " AND status = ?"; params.append(status)
    tipo = _clean(filters.get("tipo"))
    if tipo:
        tipo = validate_choice(tipo, TYPES, "Tipo")
        q += " AND tipo = ?"; params.append(tipo)
    prioridade = _clean(filters.get("prioridade"))
    if prioridade:
        prioridade = validate_choice(prioridade, PRIORITIES, "Prioridade")
        q += " AND prioridade = ?"; params.append(prioridade)
    responsavel = _clean(filters.get("responsavel"))
    if responsavel:
        q += " AND responsavel LIKE ?"; params.append(f"%{responsavel}%")
    asset_id = _clean(filters.get("asset_id"))
    if asset_id and asset_id.isdigit():
        q += " AND asset_id = ?"; params.append(int(asset_id))
    text = _clean(filters.get("q"))
    if text:
        like = f"%{text}%"
        q += " AND (titulo LIKE ? OR solicitante LIKE ? OR fornecedor LIKE ? OR codigo_rastreio LIKE ? OR destinatario LIKE ? OR cep LIKE ? OR descricao LIKE ?)"
        params.extend([like] * 7)

    sort_by = _clean(filters.get("sort_by")).lower()
    if sort_by == "prazo_asc":
        q += " ORDER BY CASE WHEN data_limite IS NULL THEN 1 ELSE 0 END, data_limite ASC, atualizado_em DESC"
    elif sort_by == "prazo_desc":
        q += " ORDER BY CASE WHEN data_limite IS NULL THEN 1 ELSE 0 END, data_limite DESC, atualizado_em DESC"
    elif sort_by == "prioridade":
        q += " ORDER BY CASE prioridade WHEN 'URGENTE' THEN 1 WHEN 'ALTA' THEN 2 WHEN 'MEDIA' THEN 3 WHEN 'BAIXA' THEN 4 ELSE 5 END ASC, atualizado_em DESC"
    elif sort_by == "titulo":
        q += " ORDER BY titulo ASC"
    else:
        q += " ORDER BY atualizado_em DESC"
    return db.execute(q, params).fetchall()


def list_tickets_paginated(filters: Dict[str, Any], page: int = 1, per_page: int = 20,
                           user_id: int = None, user_role: str = None):
    db = get_db()
    base = """FROM tickets t LEFT JOIN categories c ON c.id = t.categoria_id WHERE 1=1"""
    params: list = []

    if user_role == "operador" and user_id:
        base += " AND t.assigned_user_id = ?"
        params.append(user_id)

    status = _clean(filters.get("status"))
    show_archived = _clean(filters.get("show_archived"))
    if status:
        status = validate_choice(status, STATUSES, "Status")
        base += " AND t.status = ?"; params.append(status)
    elif show_archived == "1":
        base += " AND t.status IN ('CONCLUIDO','CANCELADO')"
    else:
        base += " AND t.status NOT IN ('CONCLUIDO','CANCELADO')"

    tipo = _clean(filters.get("tipo"))
    if tipo:
        tipo = validate_choice(tipo, TYPES, "Tipo")
        base += " AND t.tipo = ?"; params.append(tipo)
    prioridade = _clean(filters.get("prioridade"))
    if prioridade:
        prioridade = validate_choice(prioridade, PRIORITIES, "Prioridade")
        base += " AND t.prioridade = ?"; params.append(prioridade)
    responsavel = _clean(filters.get("responsavel"))
    if responsavel:
        base += " AND t.responsavel LIKE ?"; params.append(f"%{responsavel}%")
    asset_id = _clean(filters.get("asset_id"))
    if asset_id and asset_id.isdigit():
        base += " AND t.asset_id = ?"; params.append(int(asset_id))
    text_filter = _clean(filters.get("q"))
    if text_filter:
        like = f"%{text_filter}%"
        base += " AND (t.titulo LIKE ? OR t.solicitante LIKE ? OR t.fornecedor LIKE ? OR t.codigo_rastreio LIKE ? OR t.destinatario LIKE ? OR t.cep LIKE ? OR t.descricao LIKE ?)"
        params.extend([like] * 7)

    total = db.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    sort_by = _clean(filters.get("sort_by")).lower()
    order = " ORDER BY t.atualizado_em DESC"
    if sort_by == "prazo_asc":
        order = " ORDER BY CASE WHEN t.data_limite IS NULL THEN 1 ELSE 0 END, t.data_limite ASC, t.atualizado_em DESC"
    elif sort_by == "prazo_desc":
        order = " ORDER BY CASE WHEN t.data_limite IS NULL THEN 1 ELSE 0 END, t.data_limite DESC, t.atualizado_em DESC"
    elif sort_by == "prioridade":
        order = " ORDER BY CASE t.prioridade WHEN 'URGENTE' THEN 1 WHEN 'ALTA' THEN 2 WHEN 'MEDIA' THEN 3 WHEN 'BAIXA' THEN 4 ELSE 5 END ASC, t.atualizado_em DESC"
    elif sort_by == "titulo":
        order = " ORDER BY t.titulo ASC"

    q = f"SELECT t.id, t.tipo, t.titulo, t.solicitante, t.responsavel, t.prioridade, t.status, t.data_limite, t.asset_id, t.atualizado_em, t.categoria_id, COALESCE(c.nome, 'Sem categoria') AS categoria_nome {base}{order} LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    items = db.execute(q, params).fetchall()
    return items, total, total_pages


def list_tickets_by_requester(user_id: int):
    return get_db().execute(
        """SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em
           FROM tickets WHERE requester_user_id=? ORDER BY atualizado_em DESC""", (user_id,)
    ).fetchall()


def list_queue_tickets(filters=None, user_id=None, user_role=None):
    filters = filters or {}
    db = get_db()
    visible_placeholders = ",".join("?" * len(QUEUE_VISIBLE_STATUSES))
    q = f"""SELECT t.id, t.tipo, t.titulo, t.solicitante, t.responsavel, t.prioridade, t.status, t.data_limite,
                    t.requester_user_id, t.assigned_user_id, t.categoria_id, t.criado_em, t.atualizado_em,
                    u.nome as requester_name, a.nome as assigned_name,
                    c.nome as categoria_nome, c.cor as categoria_cor
             FROM tickets t
             LEFT JOIN users u ON u.id = t.requester_user_id
             LEFT JOIN users a ON a.id = t.assigned_user_id
             LEFT JOIN categories c ON c.id = t.categoria_id
             WHERE t.status IN ({visible_placeholders})"""
    params = list(QUEUE_VISIBLE_STATUSES)

    if user_role == "operador" and user_id:
        allowed = db.execute("SELECT category_id FROM user_categories WHERE user_id=?", (user_id,)).fetchall()
        allowed_ids = [r["category_id"] for r in allowed]
        if allowed_ids:
            placeholders = ",".join("?" * len(allowed_ids))
            q += f" AND t.categoria_id IN ({placeholders})"
            params.extend(allowed_ids)
        else:
            q += " AND t.assigned_user_id = ?"
            params.append(user_id)

    if _clean(filters.get("only_unassigned")) == "1":
        q += " AND t.assigned_user_id IS NULL"
    status = _clean(filters.get("status"))
    if status:
        status = validate_choice(status, QUEUE_VISIBLE_STATUSES, "Status da fila")
        q += " AND t.status = ?"; params.append(status)
    tipo = _clean(filters.get("tipo"))
    if tipo:
        q += " AND t.tipo = ?"; params.append(tipo)
    categoria_id = _clean(filters.get("categoria_id"))
    if categoria_id and categoria_id.isdigit():
        q += " AND t.categoria_id = ?"; params.append(int(categoria_id))
    text = _clean(filters.get("q"))
    if text:
        like = f"%{text}%"
        q += " AND (t.titulo LIKE ? OR t.solicitante LIKE ? OR u.nome LIKE ?)"
        params.extend([like, like, like])
    q += " ORDER BY CASE WHEN t.assigned_user_id IS NULL THEN 0 ELSE 1 END, t.criado_em ASC"
    return db.execute(q, params).fetchall()


# ── Status ───────────────────────────────────────────────────────────────

def update_status(ticket_id: int, new_status: str, detalhe: str = ""):
    db = get_db()
    new_status = validate_choice(new_status, STATUSES, "Status")
    row = db.execute("SELECT status, closed_em FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    old = row["status"]
    if old in LOCKED_STATUSES and new_status not in ("ABERTO", "EM_ANDAMENTO"):
        raise ValueError(f"Chamado {old.replace('_', ' ').title()} não pode ter status alterado diretamente.")
    permitidas = TRANSICOES_VALIDAS.get(old)
    if permitidas and new_status not in permitidas:
        raise ValueError(
            f"Transição inválida: {old.replace('_', ' ')} → {new_status.replace('_', ' ')}. "
            f"Transições permitidas: {', '.join(s.replace('_', ' ') for s in permitidas)}."
        )
    closed_em = row["closed_em"]
    if new_status in ("CONCLUIDO", "CANCELADO"):
        closed_em = _now()
    elif old in ("CONCLUIDO", "CANCELADO") and new_status not in ("CONCLUIDO", "CANCELADO"):
        closed_em = None
    db.execute("UPDATE tickets SET status = ?, closed_em = ?, atualizado_em = ? WHERE id = ?",
               (new_status, closed_em, _now(), ticket_id))
    db.commit()
    msg = f"{old} -> {new_status}" + (f". {detalhe.strip()}" if detalhe else "")
    log_event(ticket_id, "STATUS_ALTERADO", msg)


def update_fields(ticket_id: int, data: Dict[str, Any]):
    db = get_db()
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] in LOCKED_STATUSES:
        raise ValueError("Chamado bloqueado para edição. Aguardando confirmação ou já concluído.")
    fields = dict(
        responsavel=_clean(data.get("responsavel")),
        fornecedor=_clean(data.get("fornecedor")),
        centro_custo=_clean(data.get("centro_custo")),
        valor_estimado=_parse_float(data.get("valor_estimado")),
        link_pedido=_clean(data.get("link_pedido")),
        codigo_rastreio=_clean(data.get("codigo_rastreio")),
        data_limite=_validate_date_ymd(data.get("data_limite")),
        destinatario=_clean(data.get("destinatario")),
        telefone=_clean(data.get("telefone")),
        endereco=_clean(data.get("endereco")),
        cidade=_clean(data.get("cidade")),
        estado=_clean(data.get("estado")),
        cep=_clean(data.get("cep")),
        asset_id=(int(data.get("asset_id")) if str(data.get("asset_id", "")).strip().isdigit() else None),
    )
    LABELS = {
        "responsavel": "Responsável", "fornecedor": "Fornecedor",
        "centro_custo": "Centro de custo", "valor_estimado": "Valor estimado",
        "link_pedido": "Link do pedido", "codigo_rastreio": "Rastreio",
        "data_limite": "Prazo", "destinatario": "Destinatário",
        "telefone": "Telefone", "endereco": "Endereço", "cidade": "Cidade",
        "estado": "Estado", "cep": "CEP", "asset_id": "Ativo",
    }
    diffs = []
    for k, new_val in fields.items():
        old_val = t[k] if k in t.keys() else None
        if str(old_val or "") != str(new_val or ""):
            label = LABELS.get(k, k)
            diffs.append(f"{label}: '{old_val or '–'}' → '{new_val or '–'}'")

    db.execute("""UPDATE tickets SET
        responsavel=?, fornecedor=?, centro_custo=?, valor_estimado=?,
        link_pedido=?, codigo_rastreio=?, data_limite=?,
        destinatario=?, telefone=?, endereco=?, cidade=?, estado=?, cep=?, asset_id=?,
        atualizado_em=?
      WHERE id=?""",
      (fields["responsavel"], fields["fornecedor"], fields["centro_custo"], fields["valor_estimado"],
       fields["link_pedido"], fields["codigo_rastreio"], fields["data_limite"],
       fields["destinatario"], fields["telefone"], fields["endereco"], fields["cidade"],
       fields["estado"], fields["cep"], fields["asset_id"],
       _now(), ticket_id))
    db.commit()
    if diffs:
        log_event(ticket_id, "EDITADO", " | ".join(diffs))
    else:
        log_event(ticket_id, "EDITADO", "Sem alterações nos campos.")

    old_asset_id = t["asset_id"] if "asset_id" in t.keys() else None
    new_asset_id = fields["asset_id"]
    numero = t["numero_chamado"] if "numero_chamado" in t.keys() else str(ticket_id)
    if old_asset_id and old_asset_id != new_asset_id:
        _log_asset_history(old_asset_id, "DESVINCULADO_CHAMADO", f"Chamado {numero} foi desvinculado do ativo.")
    if new_asset_id and old_asset_id != new_asset_id:
        _log_asset_history(new_asset_id, "VINCULADO_CHAMADO", f"Chamado {numero} foi vinculado ao ativo.")


def finalizar_ticket(ticket_id: int, operador_nome: str = ""):
    db = get_db()
    row = db.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    if row["status"] in LOCKED_STATUSES:
        raise ValueError("Chamado já está aguardando confirmação ou concluído.")
    db.execute("UPDATE tickets SET status = 'AGUARDANDO_CONFIRMACAO', atualizado_em = ? WHERE id = ?", (_now(), ticket_id))
    db.commit()
    log_event(ticket_id, "FINALIZADO_OPERADOR", f"Aguardando confirmação do solicitante. Finalizado por {operador_nome or 'operador'}.")


def confirmar_conclusao(ticket_id: int, solicitante_nome: str = ""):
    from app.services.sla_service import gravar_tma
    from app.services.webhook_service import fire_webhooks
    db = get_db()
    row = db.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    if row["status"] != "AGUARDANDO_CONFIRMACAO":
        raise ValueError("Chamado não está aguardando confirmação.")
    t = _now()
    db.execute("UPDATE tickets SET status = 'CONCLUIDO', closed_em = ?, atualizado_em = ? WHERE id = ?", (t, t, ticket_id))
    db.commit()
    log_event(ticket_id, "CONCLUIDO_SOLICITANTE", f"Conclusão confirmada por {solicitante_nome or ''}.")
    gravar_tma(ticket_id)
    fire_webhooks("ticket.concluido", {"ticket_id": ticket_id})


def rejeitar_conclusao(ticket_id: int, motivo: str = "", solicitante_nome: str = ""):
    db = get_db()
    row = db.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    if row["status"] != "AGUARDANDO_CONFIRMACAO":
        raise ValueError("Chamado não está aguardando confirmação.")
    db.execute("UPDATE tickets SET status = 'EM_ANDAMENTO', atualizado_em = ? WHERE id = ?", (_now(), ticket_id))
    db.commit()
    msg = f"Solicitante {solicitante_nome or ''} rejeitou a conclusão." + (f" Motivo: {motivo}" if motivo else "")
    log_event(ticket_id, "CONCLUSAO_REJEITADA", msg)


# ── Atribuição ───────────────────────────────────────────────────────────

def assign_ticket(ticket_id: int, user_id: int, user_name: str = ""):
    db = get_db()
    row = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    new_status = 'EM_ANDAMENTO' if row['status'] == 'ABERTO' else row['status']
    db.execute("UPDATE tickets SET assigned_user_id=?, responsavel=?, status=?, atualizado_em=? WHERE id=?",
               (user_id, user_name or "", new_status, _now(), ticket_id))
    db.commit()
    log_event(ticket_id, "ATRIBUIDO", f"Chamado assumido por {user_name or user_id}.")


def _auto_assign(db, categoria_id: int) -> Optional[dict]:
    row = db.execute(
        """SELECT u.id, u.nome,
           (SELECT COUNT(*) FROM tickets t2
            WHERE t2.assigned_user_id=u.id
            AND t2.status NOT IN ('CONCLUIDO','CANCELADO','AGUARDANDO_INFO')) as carga
           FROM users u
           JOIN user_categories uc ON uc.user_id=u.id
           WHERE uc.category_id=? AND u.active=1 AND u.role IN ('admin','operador')
           ORDER BY carga ASC, u.nome ASC LIMIT 1""",
        (categoria_id,)
    ).fetchone()
    return dict(row) if row else None


def _fallback_assign(db, categoria_id: int) -> Optional[dict]:
    row = db.execute(
        """SELECT u.id, u.nome,
           (SELECT COUNT(*) FROM tickets t2
            WHERE t2.assigned_user_id=u.id
              AND t2.status NOT IN ('CONCLUIDO','CANCELADO','AGUARDANDO_INFO')) as carga,
           COALESCE((
               SELECT MAX(tl.criado_em)
               FROM ticket_log tl
               JOIN tickets tx ON tx.id = tl.ticket_id
               WHERE tl.evento IN ('ATRIBUIDO','ATRIBUIDO_TIMEOUT')
                 AND tx.assigned_user_id = u.id
           ), '1970-01-01 00:00:00') as ultima_atribuicao
           FROM users u
           JOIN user_categories uc ON uc.user_id = u.id
           WHERE uc.category_id = ? AND u.active = 1 AND u.role IN ('admin','operador')
           ORDER BY carga ASC, ultima_atribuicao ASC, u.nome ASC
           LIMIT 1""",
        (categoria_id,)
    ).fetchone()
    return dict(row) if row else None


def auto_assign_overdue_tickets(timeout_minutes: int = 15) -> int:
    db = get_db()
    cutoff = datetime.now() - timedelta(minutes=max(1, int(timeout_minutes or 15)))
    rows = db.execute(
        """SELECT id, titulo, categoria_id, criado_em
           FROM tickets
           WHERE assigned_user_id IS NULL
             AND status = 'ABERTO'
             AND categoria_id IS NOT NULL
           ORDER BY criado_em ASC"""
    ).fetchall()
    processed = 0
    now_s = _now()
    for row in rows:
        created_at = _parse_dt(row['criado_em'])
        if not created_at or created_at > cutoff:
            continue
        auto = _fallback_assign(db, row['categoria_id'])
        if not auto:
            log_event(row['id'], 'ASSUNCAO_TIMEOUT_SEM_OPERADOR', 'Timeout de assunção atingido, mas não há operador elegível na categoria.')
            continue
        db.execute(
            "UPDATE tickets SET assigned_user_id=?, responsavel=?, status='EM_ANDAMENTO', atualizado_em=? WHERE id=?",
            (auto['id'], auto['nome'], now_s, row['id'])
        )
        db.commit()
        log_event(row['id'], 'ATRIBUIDO_TIMEOUT', f"Chamado autoatribuído por timeout de assunção para {auto['nome']}.")
        processed += 1
    return processed


def get_overdue_tickets(today: Optional[str] = None):
    today = today or _today_ymd()
    return get_db().execute("""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite
        FROM tickets
        WHERE data_limite IS NOT NULL AND data_limite < ? AND status NOT IN ('CONCLUIDO','CANCELADO')
        ORDER BY data_limite ASC""", (today,)).fetchall()


def seed_example():
    t1 = create_ticket({"tipo": "COMPRA", "titulo": "Compra de headset", "descricao": "Headset para colaborador.",
                         "solicitante": "Service Desk", "prioridade": "ALTA", "responsavel": "Eliel",
                         "fornecedor": "Kabum", "centro_custo": "TI-001", "valor_estimado": "249.90",
                         "data_limite": _today_ymd()})
    update_status(t1, "EM_ANDAMENTO", "Iniciado.")
