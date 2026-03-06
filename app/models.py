from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from .db import get_db

STATUSES = ["ABERTO","EM_ANDAMENTO","AGUARDANDO_FORNECEDOR","AGUARDANDO_APROVACAO","ENVIADO","CONCLUIDO","CANCELADO"]
TYPES = ["COMPRA","ENVIO"]
PRIORITIES = ["BAIXA","MEDIA","ALTA","URGENTE"]

SUGGESTED_STEPS = {
    "COMPRA": [
        "Coletar especificação/quantidade",
        "Cotação / fornecedor",
        "Aprovação (centro de custo)",
        "Pedido criado + link",
        "Entrega / conferência",
        "Concluído",
    ],
    "ENVIO": [
        "Confirmar destinatário/endereço/telefone",
        "Preparar equipamento + checklist",
        "Postar / transportadora",
        "Registrar rastreio",
        "Confirmar recebimento",
        "Concluído",
    ],
}

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _today_ymd() -> str:
    return date.today().strftime("%Y-%m-%d")

def validate_choice(value: str, allowed: List[str], field: str):
    if value is None:
        raise ValueError(f"{field} é obrigatório.")
    v = value.strip().upper()
    if v not in allowed:
        raise ValueError(f"{field} inválido: '{value}'. Use: {allowed}")
    return v

def _clean(s: Optional[str]) -> str:
    return (s or "").strip()

def _parse_float(s: Optional[str]) -> Optional[float]:
    s = _clean(s)
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError("Valor estimado inválido. Use número (ex: 1500.00).")

def _validate_date_ymd(s: Optional[str]) -> Optional[str]:
    s = _clean(s)
    if not s:
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        raise ValueError("Data limite inválida. Use YYYY-MM-DD (ex: 2026-03-15).")

def log_event(ticket_id: int, evento: str, detalhe: str = ""):
    db = get_db()
    db.execute(
        "INSERT INTO ticket_log (ticket_id, evento, detalhe, criado_em) VALUES (?, ?, ?, ?)",
        (ticket_id, evento, detalhe, _now())
    )
    db.commit()

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
    """Recalcula step_order (1..n) e evita buracos."""
    db = get_db()
    rows = db.execute("SELECT id FROM ticket_steps WHERE ticket_id=? ORDER BY step_order ASC, id ASC", (ticket_id,)).fetchall()
    for i, r in enumerate(rows, start=1):
        db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (i, r["id"]))
    db.commit()

def create_ticket(data: Dict[str, Any]) -> int:
    tipo = validate_choice(data.get("tipo", ""), TYPES, "Tipo")
    prioridade = validate_choice(data.get("prioridade", ""), PRIORITIES, "Prioridade")
    titulo = _clean(data.get("titulo"))
    if not titulo:
        raise ValueError("Título é obrigatório.")

    status = "ABERTO"
    t = _now()

    payload = dict(
        tipo=tipo, titulo=titulo, descricao=_clean(data.get("descricao")), solicitante=_clean(data.get("solicitante")),
        prioridade=prioridade, status=status,
        responsavel=_clean(data.get("responsavel")), fornecedor=_clean(data.get("fornecedor")),
        centro_custo=_clean(data.get("centro_custo")), valor_estimado=_parse_float(data.get("valor_estimado")),
        link_pedido=_clean(data.get("link_pedido")), codigo_rastreio=_clean(data.get("codigo_rastreio")),
        data_limite=_validate_date_ymd(data.get("data_limite")),
        destinatario=_clean(data.get("destinatario")), telefone=_clean(data.get("telefone")), endereco=_clean(data.get("endereco")),
        cidade=_clean(data.get("cidade")), estado=_clean(data.get("estado")), cep=_clean(data.get("cep")),
        asset_id=(int(data.get("asset_id")) if str(data.get("asset_id","")).strip().isdigit() else None), requester_user_id=(int(data.get("requester_user_id")) if str(data.get("requester_user_id","")).strip().isdigit() else None), assigned_user_id=(int(data.get("assigned_user_id")) if str(data.get("assigned_user_id","")).strip().isdigit() else None), closed_em=None, criado_em=t, atualizado_em=t,
    )

    db = get_db()
    cur = db.execute("""INSERT INTO tickets (
        tipo, titulo, descricao, solicitante, prioridade, status,
        responsavel, fornecedor, centro_custo, valor_estimado, link_pedido, codigo_rastreio, data_limite,
        destinatario, telefone, endereco, cidade, estado, cep, asset_id, requester_user_id, assigned_user_id, closed_em,
        criado_em, atualizado_em
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        payload["tipo"], payload["titulo"], payload["descricao"], payload["solicitante"], payload["prioridade"], payload["status"],
        payload["responsavel"], payload["fornecedor"], payload["centro_custo"], payload["valor_estimado"], payload["link_pedido"],
        payload["codigo_rastreio"], payload["data_limite"],
        payload["destinatario"], payload["telefone"], payload["endereco"], payload["cidade"], payload["estado"], payload["cep"], payload["asset_id"], payload["requester_user_id"], payload["assigned_user_id"], payload["closed_em"],
        payload["criado_em"], payload["atualizado_em"]
    ))
    db.commit()
    ticket_id = cur.lastrowid
    log_event(ticket_id, "CRIADO", f"Chamado criado como {status}")
    _insert_steps(ticket_id, tipo)
    return ticket_id

def get_ticket(ticket_id: int):
    return get_db().execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()

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
        params.extend([like, like, like, like, like, like, like])

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

def update_status(ticket_id: int, new_status: str, detalhe: str = ""):
    db = get_db()
    new_status = validate_choice(new_status, STATUSES, "Status")
    row = db.execute("SELECT status, closed_em FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    old = row["status"]
    closed_em = row["closed_em"]
    if new_status == "CONCLUIDO":
        closed_em = _now()
    elif old == "CONCLUIDO" and new_status != "CONCLUIDO":
        closed_em = None
    db.execute("UPDATE tickets SET status = ?, closed_em = ?, atualizado_em = ? WHERE id = ?", (new_status, closed_em, _now(), ticket_id))
    db.commit()
    msg = f"{old} -> {new_status}" + (f". {detalhe.strip()}" if detalhe else "")
    log_event(ticket_id, "STATUS_ALTERADO", msg)

def update_fields(ticket_id: int, data: Dict[str, Any]):
    db = get_db()
    if not get_ticket(ticket_id):
        raise ValueError("Chamado não encontrado.")
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
        asset_id=(int(data.get("asset_id")) if str(data.get("asset_id","")).strip().isdigit() else None),
    )
    db.execute("""UPDATE tickets SET
        responsavel=?, fornecedor=?, centro_custo=?, valor_estimado=?,
        link_pedido=?, codigo_rastreio=?, data_limite=?,
        destinatario=?, telefone=?, endereco=?, cidade=?, estado=?, cep=?, asset_id=?,
        atualizado_em=?
      WHERE id=?""",
      (fields["responsavel"], fields["fornecedor"], fields["centro_custo"], fields["valor_estimado"],
       fields["link_pedido"], fields["codigo_rastreio"], fields["data_limite"],
       fields["destinatario"], fields["telefone"], fields["endereco"], fields["cidade"], fields["estado"], fields["cep"], fields["asset_id"],
       _now(), ticket_id))
    db.commit()
    log_event(ticket_id, "EDITADO", "Campos do chamado atualizados.")

def get_logs(ticket_id: int):
    return get_db().execute(
        "SELECT criado_em, evento, detalhe FROM ticket_log WHERE ticket_id=? ORDER BY criado_em ASC",
        (ticket_id,)
    ).fetchall()

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
        "SELECT COUNT(*) as c FROM attachments WHERE ticket_id=?",
        (ticket_id,)
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
        # shift orders >= ref order
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
        other = db.execute("SELECT id FROM ticket_steps WHERE ticket_id=? AND step_order=?", (ticket_id, order-1)).fetchone()
        if other:
            db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order-1, step_id))
            db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order, other["id"]))
    elif direction == "down":
        maxo = db.execute("SELECT MAX(step_order) as m FROM ticket_steps WHERE ticket_id=?", (ticket_id,)).fetchone()["m"] or 1
        if order < maxo:
            other = db.execute("SELECT id FROM ticket_steps WHERE ticket_id=? AND step_order=?", (ticket_id, order+1)).fetchone()
            if other:
                db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order+1, step_id))
                db.execute("UPDATE ticket_steps SET step_order=? WHERE id=?", (order, other["id"]))
    db.execute("UPDATE tickets SET atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    normalize_steps(ticket_id)

def get_overdue_tickets(today: Optional[str] = None):
    db = get_db()
    today = today or _today_ymd()
    return db.execute("""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite
        FROM tickets
        WHERE data_limite IS NOT NULL AND data_limite < ? AND status NOT IN ('CONCLUIDO','CANCELADO')
        ORDER BY data_limite ASC""", (today,)).fetchall()

def dashboard_stats():
    db = get_db()
    rows = db.execute("SELECT status, COUNT(*) as total FROM tickets GROUP BY status").fetchall()
    by_status = {r["status"]: r["total"] for r in rows}
    total = db.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]
    today = _today_ymd()
    overdue_rows = get_overdue_tickets(today)
    overdue = len(overdue_rows)
    upcoming = db.execute("""SELECT id, titulo, status, prioridade, responsavel, data_limite
      FROM tickets WHERE data_limite IS NOT NULL AND data_limite >= ? AND status NOT IN ('CONCLUIDO','CANCELADO')
      ORDER BY data_limite ASC LIMIT 10""", (today,)).fetchall()
    return {"total": total, "by_status": by_status, "overdue": overdue, "overdue_rows": overdue_rows, "upcoming": upcoming, "today": today}

def seed_example():
    t1 = create_ticket({"tipo":"COMPRA","titulo":"Compra de headset","descricao":"Headset para colaborador do atendimento.",
                        "solicitante":"Service Desk","prioridade":"ALTA","responsavel":"Eliel","fornecedor":"Kabum",
                        "centro_custo":"TI-001","valor_estimado":"249.90","link_pedido":"https://exemplo.local/pedido/123",
                        "data_limite":_today_ymd()})
    update_status(t1, "AGUARDANDO_APROVACAO", "Aguardando aprovação do gestor.")
    t2 = create_ticket({"tipo":"ENVIO","titulo":"Envio de notebook - filial RJ","descricao":"Enviar notebook com carregador e mochila.",
                        "solicitante":"Patrimônio","prioridade":"MEDIA","responsavel":"Iago","codigo_rastreio":"BR123EXEMPLO",
                        "data_limite":_today_ymd(),"destinatario":"Fulano da Silva","telefone":"(21) 99999-0000",
                        "endereco":"Rua Exemplo, 123","cidade":"Rio de Janeiro","estado":"RJ","cep":"20000-000"})
    update_status(t2, "ENVIADO", "Postado. Rastreio BR123EXEMPLO.")


def _days_between(date_ymd: str, today_ymd: str) -> int:
    d1 = datetime.strptime(date_ymd, "%Y-%m-%d").date()
    d2 = datetime.strptime(today_ymd, "%Y-%m-%d").date()
    return (d2 - d1).days

def dashboard_stats_advanced():
    """Dashboard mais avançado (sem libs externas).
    Reaproveita dados do banco e calcula:
    - KPIs por tipo/prioridade/status
    - Atrasados com dias de atraso
    - Aging (idade do chamado) em faixas
    - Top responsáveis
    - Concluídos nos últimos 30 dias (aprox. via logs)
    """
    db = get_db()
    today = _today_ymd()

    total = db.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]

    # Por status/tipo/prioridade
    by_status = {r["status"]: r["total"] for r in db.execute("SELECT status, COUNT(*) as total FROM tickets GROUP BY status").fetchall()}
    by_tipo = {r["tipo"]: r["total"] for r in db.execute("SELECT tipo, COUNT(*) as total FROM tickets GROUP BY tipo").fetchall()}
    by_prioridade = {r["prioridade"]: r["total"] for r in db.execute("SELECT prioridade, COUNT(*) as total FROM tickets GROUP BY prioridade").fetchall()}

    # Atrasados
    overdue_rows = db.execute("""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite, criado_em
        FROM tickets
        WHERE data_limite IS NOT NULL AND data_limite < ? AND status NOT IN ('CONCLUIDO','CANCELADO')
        ORDER BY data_limite ASC""", (today,)).fetchall()
    overdue = []
    for r in overdue_rows:
        try:
            days_late = _days_between(r["data_limite"], today)
        except Exception:
            days_late = None
        overdue.append({**dict(r), "days_late": days_late})

    # Próximos vencimentos (até 14 dias)
    upcoming_rows = db.execute("""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite
      FROM tickets
      WHERE data_limite IS NOT NULL AND data_limite >= ? AND status NOT IN ('CONCLUIDO','CANCELADO')
      ORDER BY data_limite ASC LIMIT 20""", (today,)).fetchall()
    upcoming = []
    for r in upcoming_rows:
        try:
            days_to = -_days_between(r["data_limite"], today)  # futuro => negativo
            days_to = abs(days_to)
        except Exception:
            days_to = None
        upcoming.append({**dict(r), "days_to_due": days_to})

    # Aging (idade em dias) para abertos (não concluídos/cancelados)
    open_rows = db.execute("""SELECT id, titulo, tipo, status, prioridade, responsavel, criado_em
        FROM tickets
        WHERE status NOT IN ('CONCLUIDO','CANCELADO')
        ORDER BY criado_em ASC""").fetchall()
    aging_buckets = {"0-2":0, "3-7":0, "8-14":0, "15-30":0, "31+":0}
    oldest = []
    for r in open_rows:
        created = (r["criado_em"] or "")[:10]
        try:
            age = _days_between(created, today)
        except Exception:
            age = None
        bucket = None
        if age is None:
            bucket = None
        elif age <= 2:
            bucket = "0-2"
        elif age <= 7:
            bucket = "3-7"
        elif age <= 14:
            bucket = "8-14"
        elif age <= 30:
            bucket = "15-30"
        else:
            bucket = "31+"
        if bucket:
            aging_buckets[bucket] += 1
        oldest.append({**dict(r), "age_days": age})
    oldest = [o for o in oldest if o["age_days"] is not None]
    oldest.sort(key=lambda x: x["age_days"], reverse=True)
    oldest = oldest[:15]

    # Top responsáveis (abertos)
    top_resp_rows = db.execute("""SELECT COALESCE(NULLIF(responsavel,''), '(sem responsável)') as resp, COUNT(*) as total
        FROM tickets
        WHERE status NOT IN ('CONCLUIDO','CANCELADO')
        GROUP BY resp ORDER BY total DESC, resp ASC LIMIT 10""").fetchall()
    top_responsaveis = [dict(r) for r in top_resp_rows]

    # Concluídos últimos 30 dias (via logs de STATUS_ALTERADO contendo '-> CONCLUIDO')
    # Observação: se você concluir sem log, não entra aqui.
    since = (datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=30)).strftime("%Y-%m-%d")
    done_rows = db.execute("""SELECT criado_em FROM ticket_log
        WHERE evento='STATUS_ALTERADO' AND detalhe LIKE '%-> CONCLUIDO%' AND substr(criado_em,1,10) >= ?""", (since,)).fetchall()
    concluded_30d = len(done_rows)

    # Pequeno funil (abertos vs concluídos)
    open_count = db.execute("""SELECT COUNT(*) as c FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO')""").fetchone()["c"]
    closed_count = db.execute("""SELECT COUNT(*) as c FROM tickets WHERE status IN ('CONCLUIDO','CANCELADO')""").fetchone()["c"]

    return {
        "today": today,
        "total": total,
        "by_status": by_status,
        "by_tipo": by_tipo,
        "by_prioridade": by_prioridade,
        "open_count": open_count,
        "closed_count": closed_count,
        "overdue": overdue,
        "upcoming": upcoming,
        "aging_buckets": aging_buckets,
        "oldest": oldest,
        "top_responsaveis": top_responsaveis,
        "concluded_30d": concluded_30d,
    }


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def ticket_report_metrics(start_date=None, end_date=None, sla_days=3):
    db = get_db()
    q = """SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, asset_id, criado_em, atualizado_em, closed_em
           FROM tickets WHERE 1=1"""
    params = []
    if start_date:
        q += " AND substr(criado_em,1,10) >= ?"
        params.append(start_date)
    if end_date:
        q += " AND substr(criado_em,1,10) <= ?"
        params.append(end_date)
    q += " ORDER BY criado_em DESC"
    rows = db.execute(q, params).fetchall()
    items = [dict(r) for r in rows]
    resolved = []
    for item in items:
        c = _parse_dt(item.get("criado_em"))
        f = _parse_dt(item.get("closed_em"))
        if c and f:
            hours = round((f - c).total_seconds() / 3600.0, 2)
            days = round(hours / 24.0, 2)
            item["resolution_hours"] = hours
            item["resolution_days"] = days
            item["within_sla"] = days <= sla_days
            resolved.append(item)
        else:
            item["resolution_hours"] = None
            item["resolution_days"] = None
            item["within_sla"] = None
    avg_days = round(sum(i["resolution_days"] for i in resolved) / len(resolved), 2) if resolved else 0
    within_sla_count = sum(1 for i in resolved if i["within_sla"])
    outside_sla_count = sum(1 for i in resolved if i["within_sla"] is False)
    within_sla_pct = round((within_sla_count / len(resolved)) * 100, 1) if resolved else 0
    by_status, by_tipo, by_responsavel = {}, {}, {}
    for item in items:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        by_tipo[item["tipo"]] = by_tipo.get(item["tipo"], 0) + 1
        resp = item["responsavel"] or "(sem responsável)"
        by_responsavel[resp] = by_responsavel.get(resp, 0) + 1
    top_responsaveis = sorted(by_responsavel.items(), key=lambda x: (-x[1], x[0]))[:10]
    return {
        "items": items,
        "resolved_items": resolved,
        "total": len(items),
        "resolved_total": len(resolved),
        "avg_resolution_days": avg_days,
        "within_sla_count": within_sla_count,
        "outside_sla_count": outside_sla_count,
        "within_sla_pct": within_sla_pct,
        "by_status": by_status,
        "by_tipo": by_tipo,
        "top_responsaveis": top_responsaveis,
        "start_date": start_date,
        "end_date": end_date,
        "sla_days": sla_days,
    }


def list_queue_tickets(filters=None):
    filters = filters or {}
    db = get_db()
    q = """SELECT t.id, t.tipo, t.titulo, t.solicitante, t.responsavel, t.prioridade, t.status, t.data_limite,
                    t.requester_user_id, t.assigned_user_id, t.criado_em, t.atualizado_em,
                    u.nome as requester_name, a.nome as assigned_name
             FROM tickets t
             LEFT JOIN users u ON u.id = t.requester_user_id
             LEFT JOIN users a ON a.id = t.assigned_user_id
             WHERE 1=1"""
    params = []
    if _clean(filters.get("only_unassigned")) == "1":
        q += " AND t.assigned_user_id IS NULL"
    status = _clean(filters.get("status"))
    if status:
        q += " AND t.status = ?"; params.append(status)
    tipo = _clean(filters.get("tipo"))
    if tipo:
        q += " AND t.tipo = ?"; params.append(tipo)
    text = _clean(filters.get("q"))
    if text:
        like = f"%{text}%"
        q += " AND (t.titulo LIKE ? OR t.solicitante LIKE ? OR u.nome LIKE ?)"
        params.extend([like, like, like])
    q += " ORDER BY CASE WHEN t.assigned_user_id IS NULL THEN 0 ELSE 1 END, t.criado_em ASC"
    return db.execute(q, params).fetchall()

def list_tickets_by_requester(user_id: int):
    db = get_db()
    return db.execute("""SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em
                         FROM tickets WHERE requester_user_id=? ORDER BY atualizado_em DESC""", (user_id,)).fetchall()

def assign_ticket(ticket_id: int, user_id: int, user_name: str = ""):
    db = get_db()
    row = db.execute("SELECT id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    db.execute("UPDATE tickets SET assigned_user_id=?, responsavel=?, atualizado_em=? WHERE id=?", (user_id, user_name or "", _now(), ticket_id))
    db.commit()
    log_event(ticket_id, "ATRIBUIDO", f"Chamado assumido por {user_name or user_id}.")


def list_tickets_paginated(filters: Dict[str, Any], page: int = 1, per_page: int = 20):
    """Versão paginada de list_tickets. Retorna (items, total, total_pages)."""
    db = get_db()
    base = """FROM tickets WHERE 1=1"""
    params: list = []
    status = _clean(filters.get("status"))
    if status:
        status = validate_choice(status, STATUSES, "Status")
        base += " AND status = ?"; params.append(status)
    tipo = _clean(filters.get("tipo"))
    if tipo:
        tipo = validate_choice(tipo, TYPES, "Tipo")
        base += " AND tipo = ?"; params.append(tipo)
    prioridade = _clean(filters.get("prioridade"))
    if prioridade:
        prioridade = validate_choice(prioridade, PRIORITIES, "Prioridade")
        base += " AND prioridade = ?"; params.append(prioridade)
    responsavel = _clean(filters.get("responsavel"))
    if responsavel:
        base += " AND responsavel LIKE ?"; params.append(f"%{responsavel}%")
    asset_id = _clean(filters.get("asset_id"))
    if asset_id and asset_id.isdigit():
        base += " AND asset_id = ?"; params.append(int(asset_id))
    text = _clean(filters.get("q"))
    if text:
        like = f"%{text}%"
        base += " AND (titulo LIKE ? OR solicitante LIKE ? OR fornecedor LIKE ? OR codigo_rastreio LIKE ? OR destinatario LIKE ? OR cep LIKE ? OR descricao LIKE ?)"
        params.extend([like, like, like, like, like, like, like])

    total = db.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    sort_by = _clean(filters.get("sort_by")).lower()
    order = " ORDER BY atualizado_em DESC"
    if sort_by == "prazo_asc":
        order = " ORDER BY CASE WHEN data_limite IS NULL THEN 1 ELSE 0 END, data_limite ASC, atualizado_em DESC"
    elif sort_by == "prazo_desc":
        order = " ORDER BY CASE WHEN data_limite IS NULL THEN 1 ELSE 0 END, data_limite DESC, atualizado_em DESC"
    elif sort_by == "prioridade":
        order = " ORDER BY CASE prioridade WHEN 'URGENTE' THEN 1 WHEN 'ALTA' THEN 2 WHEN 'MEDIA' THEN 3 WHEN 'BAIXA' THEN 4 ELSE 5 END ASC, atualizado_em DESC"
    elif sort_by == "titulo":
        order = " ORDER BY titulo ASC"

    q = f"SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, asset_id, atualizado_em {base}{order} LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    items = db.execute(q, params).fetchall()
    return items, total, total_pages
