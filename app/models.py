from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from .db import get_db

STATUSES = ["ABERTO","EM_ANDAMENTO","AGUARDANDO_FORNECEDOR","AGUARDANDO_APROVACAO","ENVIADO","AGUARDANDO_CONFIRMACAO","AGUARDANDO_INFO","CONCLUIDO","CANCELADO"]
CLASSIFICATIONS = ["REQUISICAO", "INCIDENTE"]
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

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None

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

def _next_numero(db, classificacao: str) -> str:
    prefix = "REQ" if classificacao == "REQUISICAO" else "INC"
    row = db.execute(
        "SELECT COUNT(*) as total FROM tickets WHERE classificacao = ?", (classificacao,)
    ).fetchone()
    seq = (row["total"] or 0) + 1
    return f"{prefix}-{seq:04d}"

def create_ticket(data: Dict[str, Any]) -> int:
    tipo = data.get("tipo") or "GERAL"
    classificacao = data.get("classificacao", "REQUISICAO")
    if classificacao not in CLASSIFICATIONS:
        classificacao = "REQUISICAO"
    prioridade = validate_choice(data.get("prioridade", ""), PRIORITIES, "Prioridade")
    titulo = _clean(data.get("titulo"))
    if not titulo:
        raise ValueError("Título é obrigatório.")

    categoria_id = (int(data.get("categoria_id")) if str(data.get("categoria_id","")).strip().isdigit() else None)
    t = _now()

    # SLA automático pela categoria
    sla_deadline = calc_sla_deadline(categoria_id, t) if categoria_id else None

    # Status inicial: verifica se precisa aprovação
    status = "ABERTO"
    if categoria_id:
        db_pre = get_db()
        cat = db_pre.execute("SELECT requer_aprovacao, valor_aprovacao_limite FROM categories WHERE id=?", (categoria_id,)).fetchone()
        if cat and cat["requer_aprovacao"]:
            valor = _parse_float(data.get("valor_estimado"))
            limite = cat["valor_aprovacao_limite"]
            if not limite or (valor and valor >= limite):
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
        asset_id=(int(data.get("asset_id")) if str(data.get("asset_id","")).strip().isdigit() else None),
        categoria_id=categoria_id,
        requester_user_id=(int(data.get("requester_user_id")) if str(data.get("requester_user_id","")).strip().isdigit() else None),
        assigned_user_id=(int(data.get("assigned_user_id")) if str(data.get("assigned_user_id","")).strip().isdigit() else None),
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

    # Fila por categoria: o chamado nasce visível para a equipe elegível.
    # A atribuição automática fica como fallback por timeout no scheduler.
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


def _auto_assign(db, categoria_id: int) -> Optional[dict]:
    """Retorna operador com menor carga ativa na categoria, ou None."""
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
    """
    Seleciona o próximo operador elegível para fallback automático.
    Critérios: menor carga ativa e quem está há mais tempo sem receber atribuição.
    """
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
    """
    Atribui automaticamente chamados ABERTOS/sem responsável que ficaram além do timeout.
    Retorna quantidade de chamados processados.
    """
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

LOCKED_STATUSES = {"AGUARDANDO_CONFIRMACAO", "CONCLUIDO"}

def update_status(ticket_id: int, new_status: str, detalhe: str = ""):
    db = get_db()
    new_status = validate_choice(new_status, STATUSES, "Status")
    row = db.execute("SELECT status, closed_em FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    old = row["status"]
    if old in LOCKED_STATUSES and new_status not in ("ABERTO", "EM_ANDAMENTO"):
        # only allow unlock via confirm/reject routes, not generic status update
        raise ValueError(f"Chamado {old.replace('_',' ').title()} não pode ter status alterado diretamente.")
    closed_em = row["closed_em"]
    if new_status == "CONCLUIDO":
        closed_em = _now()
    elif old == "CONCLUIDO" and new_status != "CONCLUIDO":
        closed_em = None
    db.execute("UPDATE tickets SET status = ?, closed_em = ?, atualizado_em = ? WHERE id = ?", (new_status, closed_em, _now(), ticket_id))
    db.commit()
    msg = f"{old} -> {new_status}" + (f". {detalhe.strip()}" if detalhe else "")
    log_event(ticket_id, "STATUS_ALTERADO", msg)

def finalizar_ticket(ticket_id: int, operador_nome: str = ""):
    """Operador finaliza: vai para AGUARDANDO_CONFIRMACAO (trava edição)."""
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
    """Solicitante confirma: CONCLUIDO definitivo."""
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
    """Solicitante rejeita: volta para EM_ANDAMENTO."""
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
        asset_id=(int(data.get("asset_id")) if str(data.get("asset_id","")).strip().isdigit() else None),
    )
    # Gera diff legível campo a campo
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
       fields["destinatario"], fields["telefone"], fields["endereco"], fields["cidade"], fields["estado"], fields["cep"], fields["asset_id"],
       _now(), ticket_id))
    db.commit()
    if diffs:
        log_event(ticket_id, "EDITADO", " | ".join(diffs))
    else:
        log_event(ticket_id, "EDITADO", "Sem alterações nos campos.")

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

def dashboard_stats_advanced(user_id: int = None, user_role: str = None):
    """Dashboard mais avançado (sem libs externas).
    Quando user_role='operador', filtra apenas chamados do próprio usuário.
    """
    db = get_db()
    today = _today_ymd()

    # Filtro de escopo: operador vê só seus chamados
    scope_sql = ""
    scope_params: list = []
    if user_role == "operador" and user_id:
        scope_sql = " AND assigned_user_id = ?"
        scope_params = [user_id]

    def qone(sql, params=()):
        return db.execute(sql, list(params)).fetchone()
    def qall(sql, params=()):
        return db.execute(sql, list(params)).fetchall()

    total = qone(f"SELECT COUNT(*) as c FROM tickets WHERE 1=1{scope_sql}", scope_params)["c"]

    # Por status/tipo/prioridade
    by_status = {r["status"]: r["total"] for r in qall(f"SELECT status, COUNT(*) as total FROM tickets WHERE 1=1{scope_sql} GROUP BY status", scope_params)}
    by_tipo = {r["tipo"]: r["total"] for r in qall(f"SELECT tipo, COUNT(*) as total FROM tickets WHERE 1=1{scope_sql} GROUP BY tipo", scope_params)}
    by_prioridade = {r["prioridade"]: r["total"] for r in qall(f"SELECT prioridade, COUNT(*) as total FROM tickets WHERE 1=1{scope_sql} GROUP BY prioridade", scope_params)}

    # Atrasados
    overdue_rows = qall(f"""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite, criado_em
        FROM tickets
        WHERE data_limite IS NOT NULL AND data_limite < ? AND status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
        ORDER BY data_limite ASC""", [today] + scope_params)
    overdue = []
    for r in overdue_rows:
        try:
            days_late = _days_between(r["data_limite"], today)
        except Exception:
            days_late = None
        overdue.append({**dict(r), "days_late": days_late})

    # Próximos vencimentos (até 14 dias)
    upcoming_rows = qall(f"""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite
      FROM tickets
      WHERE data_limite IS NOT NULL AND data_limite >= ? AND status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
      ORDER BY data_limite ASC LIMIT 20""", [today] + scope_params)
    upcoming = []
    for r in upcoming_rows:
        try:
            days_to = -_days_between(r["data_limite"], today)  # futuro => negativo
            days_to = abs(days_to)
        except Exception:
            days_to = None
        upcoming.append({**dict(r), "days_to_due": days_to})

    # Aging (idade em dias) para abertos (não concluídos/cancelados)
    open_rows = qall(f"""SELECT id, titulo, tipo, status, prioridade, responsavel, criado_em
        FROM tickets
        WHERE status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
        ORDER BY criado_em ASC""", scope_params)
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
    top_resp_rows = qall(f"""SELECT COALESCE(NULLIF(responsavel,''), '(sem responsável)') as resp, COUNT(*) as total
        FROM tickets
        WHERE status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
        GROUP BY resp ORDER BY total DESC, resp ASC LIMIT 10""", scope_params)
    top_responsaveis = [dict(r) for r in top_resp_rows]

    # Concluídos últimos 30 dias
    since = (datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=30)).strftime("%Y-%m-%d")
    done_rows = qall(f"""SELECT tl.criado_em FROM ticket_log tl
        JOIN tickets t ON t.id = tl.ticket_id
        WHERE tl.evento='CONCLUIDO_SOLICITANTE' AND substr(tl.criado_em,1,10) >= ?{scope_sql.replace('assigned_user_id','t.assigned_user_id')}""",
        [since] + scope_params)
    concluded_30d = len(done_rows)

    # Funil (abertos vs concluídos)
    open_count  = qone(f"SELECT COUNT(*) as c FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}", scope_params)["c"]
    closed_count = qone(f"SELECT COUNT(*) as c FROM tickets WHERE status IN ('CONCLUIDO','CANCELADO'){scope_sql}", scope_params)["c"]

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


def list_queue_tickets(filters=None, user_id=None, user_role=None):
    filters = filters or {}
    db = get_db()
    q = """SELECT t.id, t.tipo, t.titulo, t.solicitante, t.responsavel, t.prioridade, t.status, t.data_limite,
                    t.requester_user_id, t.assigned_user_id, t.categoria_id, t.criado_em, t.atualizado_em,
                    u.nome as requester_name, a.nome as assigned_name,
                    c.nome as categoria_nome, c.cor as categoria_cor
             FROM tickets t
             LEFT JOIN users u ON u.id = t.requester_user_id
             LEFT JOIN users a ON a.id = t.assigned_user_id
             LEFT JOIN categories c ON c.id = t.categoria_id
             WHERE 1=1"""
    params = []

    # Triagem automática: operadores só veem chamados das suas categorias
    if user_role == "operador" and user_id:
        allowed = db.execute(
            "SELECT category_id FROM user_categories WHERE user_id=?", (user_id,)
        ).fetchall()
        allowed_ids = [r["category_id"] for r in allowed]
        if allowed_ids:
            placeholders = ",".join("?" * len(allowed_ids))
            q += f" AND t.categoria_id IN ({placeholders})"
            params.extend(allowed_ids)
        # se não tem nenhuma categoria configurada, operador vê tudo

    if _clean(filters.get("only_unassigned")) == "1":
        q += " AND t.assigned_user_id IS NULL"
    status = _clean(filters.get("status"))
    if status:
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

def list_tickets_by_requester(user_id: int):
    db = get_db()
    return db.execute("""SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em
                         FROM tickets WHERE requester_user_id=? ORDER BY atualizado_em DESC""", (user_id,)).fetchall()

def assign_ticket(ticket_id: int, user_id: int, user_name: str = ""):
    db = get_db()
    row = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise ValueError("Chamado não encontrado.")
    new_status = 'EM_ANDAMENTO' if row['status'] == 'ABERTO' else row['status']
    db.execute("UPDATE tickets SET assigned_user_id=?, responsavel=?, status=?, atualizado_em=? WHERE id=?", (user_id, user_name or "", new_status, _now(), ticket_id))
    db.commit()
    log_event(ticket_id, "ATRIBUIDO", f"Chamado assumido por {user_name or user_id}.")


def list_tickets_paginated(filters: Dict[str, Any], page: int = 1, per_page: int = 20,
                           user_id: int = None, user_role: str = None):
    """Versão paginada de list_tickets. Retorna (items, total, total_pages)."""
    db = get_db()
    base = """FROM tickets t LEFT JOIN categories c ON c.id = t.categoria_id WHERE 1=1"""
    params: list = []

    # Na aba principal, operador vê apenas os chamados assumidos por ele.
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
        params.extend([like, like, like, like, like, like, like])

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

# ── Categorias ────────────────────────────────────────────────────────────────

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
        db.execute(
            "INSERT OR IGNORE INTO user_categories (user_id, category_id) VALUES (?, ?)",
            (user_id, cid)
        )
    db.commit()

# ══════════════════════════════════════════════════════════════════════════════
# NOVAS MELHORIAS
# ══════════════════════════════════════════════════════════════════════════════

# ── SLA ───────────────────────────────────────────────────────────────────────

def calc_sla_deadline(categoria_id: int, criado_em: str = None) -> Optional[str]:
    """Calcula o prazo SLA baseado na categoria. Retorna None se não configurado."""
    if not categoria_id:
        return None
    db = get_db()
    row = db.execute("SELECT sla_horas FROM categories WHERE id=?", (categoria_id,)).fetchone()
    if not row or not row["sla_horas"]:
        return None
    from datetime import datetime, timedelta
    base = datetime.strptime((criado_em or _now())[:19], "%Y-%m-%d %H:%M:%S")
    deadline = base + timedelta(hours=row["sla_horas"])
    return deadline.strftime("%Y-%m-%d %H:%M:%S")

def get_sla_status(ticket) -> str:
    """Retorna 'ok', 'warning' (<=20% do prazo restante) ou 'breach' (vencido)."""
    if not ticket["sla_deadline"] or ticket["status"] in ("CONCLUIDO", "CANCELADO"):
        return "none"
    from datetime import datetime
    now = datetime.now()
    try:
        criado = datetime.strptime(str(ticket["criado_em"])[:19], "%Y-%m-%d %H:%M:%S")
        deadline = datetime.strptime(str(ticket["sla_deadline"])[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "none"
    total = (deadline - criado).total_seconds()
    remaining = (deadline - now).total_seconds()
    if remaining < 0:
        return "breach"
    if total > 0 and (remaining / total) <= 0.20:
        return "warning"
    return "ok"

# ── Comentários / Notas internas ──────────────────────────────────────────────

def add_comment(ticket_id: int, user_id: int, user_nome: str, conteudo: str, interno: bool = False) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO ticket_comments (ticket_id, user_id, user_nome, conteudo, interno, criado_em) VALUES (?,?,?,?,?,?)",
        (ticket_id, user_id, user_nome, conteudo.strip(), 1 if interno else 0, _now())
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

def delete_comment(comment_id: int, user_id: int):
    db = get_db()
    db.execute("DELETE FROM ticket_comments WHERE id=? AND user_id=?", (comment_id, user_id))
    db.commit()

# ── Transferência de chamado ──────────────────────────────────────────────────

def transfer_ticket(ticket_id: int, para_user_id: int, para_user_nome: str,
                    de_user_id: int = None, de_user_nome: str = "", motivo: str = ""):
    db = get_db()
    t = db.execute("SELECT id, assigned_user_id, responsavel FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    db.execute(
        "UPDATE tickets SET assigned_user_id=?, responsavel=?, atualizado_em=? WHERE id=?",
        (para_user_id, para_user_nome, _now(), ticket_id)
    )
    db.execute(
        """INSERT INTO ticket_transfers
           (ticket_id, de_user_id, de_user_nome, para_user_id, para_user_nome, motivo, transferido_em)
           VALUES (?,?,?,?,?,?,?)""",
        (ticket_id, de_user_id, de_user_nome or "", para_user_id, para_user_nome, motivo, _now())
    )
    db.commit()
    log_event(ticket_id, "TRANSFERIDO", f"De '{de_user_nome or '?'}' para '{para_user_nome}'. {motivo}")

def get_transfers(ticket_id: int):
    return get_db().execute(
        "SELECT * FROM ticket_transfers WHERE ticket_id=? ORDER BY transferido_em DESC", (ticket_id,)
    ).fetchall()

# ── Reabertura de chamado ─────────────────────────────────────────────────────

def reabrir_ticket(ticket_id: int, user_nome: str = ""):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] not in ("CONCLUIDO", "CANCELADO"):
        raise ValueError("Apenas chamados concluídos ou cancelados podem ser reabertos.")
    db.execute(
        "UPDATE tickets SET status='ABERTO', closed_em=NULL, reaberto_em=?, atualizado_em=? WHERE id=?",
        (_now(), _now(), ticket_id)
    )
    db.commit()
    log_event(ticket_id, "REABERTO", f"Chamado reaberto por {user_nome}.")

def devolver_ao_solicitante(ticket_id: int, operador_nome: str, motivo: str):
    """Operador devolve o chamado ao solicitante pedindo informações adicionais."""
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] in ("CONCLUIDO", "CANCELADO"):
        raise ValueError("Chamado encerrado não pode ser devolvido.")
    db.execute(
        "UPDATE tickets SET status='AGUARDANDO_INFO', motivo_devolucao=?, atualizado_em=? WHERE id=?",
        (motivo.strip(), _now(), ticket_id)
    )
    db.commit()
    log_event(ticket_id, "DEVOLVIDO", f"Devolvido por {operador_nome}. Motivo: {motivo[:120]}")

def reenviar_pelo_solicitante(ticket_id: int, solicitante_nome: str, complemento: str = ""):
    """Solicitante complementa informações e reenvia — volta para o responsável atual (não para a fila)."""
    db = get_db()
    t = db.execute("SELECT id, status, assigned_user_id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    if t["status"] != "AGUARDANDO_INFO":
        raise ValueError("Chamado não está aguardando informações.")
    # Se tem responsável atribuído, volta para EM_ANDAMENTO; senão volta para ABERTO
    novo_status = "EM_ANDAMENTO" if t["assigned_user_id"] else "ABERTO"
    db.execute(
        "UPDATE tickets SET status=?, motivo_devolucao=NULL, atualizado_em=? WHERE id=?",
        (novo_status, _now(), ticket_id)
    )
    db.commit()
    detalhe = f"Solicitante {solicitante_nome} complementou as informações e reenviou."
    if complemento:
        detalhe += f" Complemento: {complemento[:200]}"
    log_event(ticket_id, "REENVIADO", detalhe)

# ── Aprovação ─────────────────────────────────────────────────────────────────

def solicitar_aprovacao(ticket_id: int, solicitante_nome: str = ""):
    """Muda status para AGUARDANDO_APROVACAO."""
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    db.execute("UPDATE tickets SET status='AGUARDANDO_APROVACAO', atualizado_em=? WHERE id=?", (_now(), ticket_id))
    db.commit()
    log_event(ticket_id, "AGUARDANDO_APROVACAO", f"Aprovação solicitada por {solicitante_nome}.")

def aprovar_ticket(ticket_id: int, aprovador_id: int, aprovador_nome: str):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    db.execute(
        "UPDATE tickets SET status='ABERTO', aprovado_por=?, aprovado_em=?, aprovador_user_id=?, atualizado_em=? WHERE id=?",
        (aprovador_nome, _now(), aprovador_id, _now(), ticket_id)
    )
    db.commit()
    log_event(ticket_id, "APROVADO", f"Aprovado por {aprovador_nome}.")

def reprovar_ticket(ticket_id: int, aprovador_nome: str, motivo: str = ""):
    db = get_db()
    t = db.execute("SELECT id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise ValueError("Chamado não encontrado.")
    db.execute(
        "UPDATE tickets SET status='CANCELADO', aprovado_por=?, aprovado_em=?, atualizado_em=? WHERE id=?",
        (aprovador_nome, _now(), _now(), ticket_id)
    )
    db.commit()
    log_event(ticket_id, "REPROVADO", f"Reprovado por {aprovador_nome}. {motivo}")

def precisa_aprovacao(ticket_id: int) -> bool:
    """Verifica se a categoria do chamado exige aprovação."""
    db = get_db()
    row = db.execute(
        """SELECT c.requer_aprovacao, c.valor_aprovacao_limite, t.valor_estimado
           FROM tickets t LEFT JOIN categories c ON c.id=t.categoria_id
           WHERE t.id=?""", (ticket_id,)
    ).fetchone()
    if not row or not row["requer_aprovacao"]:
        return False
    limite = row["valor_aprovacao_limite"]
    if limite and row["valor_estimado"]:
        return float(row["valor_estimado"]) >= float(limite)
    return bool(row["requer_aprovacao"])

# ── TMA (Tempo Médio de Atendimento) ─────────────────────────────────────────

def calcular_tma_minutos(ticket_id: int) -> Optional[int]:
    """Calcula minutos entre abertura e conclusão do chamado."""
    db = get_db()
    t = db.execute("SELECT criado_em, closed_em FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t or not t["closed_em"]:
        return None
    from datetime import datetime
    try:
        inicio = datetime.strptime(str(t["criado_em"])[:19], "%Y-%m-%d %H:%M:%S")
        fim    = datetime.strptime(str(t["closed_em"])[:19], "%Y-%m-%d %H:%M:%S")
        return max(0, int((fim - inicio).total_seconds() / 60))
    except Exception:
        return None

def gravar_tma(ticket_id: int):
    mins = calcular_tma_minutos(ticket_id)
    if mins is not None:
        get_db().execute("UPDATE tickets SET tma_minutos=? WHERE id=?", (mins, ticket_id))
        get_db().commit()

def tma_stats(user_id: int = None, categoria_id: int = None) -> dict:
    db = get_db()
    q = "SELECT tma_minutos FROM tickets WHERE status='CONCLUIDO' AND tma_minutos IS NOT NULL"
    params = []
    if user_id:
        q += " AND assigned_user_id=?"; params.append(user_id)
    if categoria_id:
        q += " AND categoria_id=?"; params.append(categoria_id)
    rows = db.execute(q, params).fetchall()
    if not rows:
        return {"media": None, "minimo": None, "maximo": None, "total": 0}
    vals = [r["tma_minutos"] for r in rows]
    return {
        "media": round(sum(vals) / len(vals)),
        "minimo": min(vals),
        "maximo": max(vals),
        "total": len(vals)
    }

# ── Category updates (SLA + template + checklist) ────────────────────────────

def update_category_full(category_id: int, nome: str, descricao: str, cor: str, ativo: bool,
                          campos_visiveis: str = None, sla_horas: int = None,
                          checklist_padrao: str = None, template_descricao: str = None,
                          requer_aprovacao: bool = False, valor_aprovacao_limite: float = None):
    db = get_db()
    db.execute(
        """UPDATE categories SET nome=?, descricao=?, cor=?, ativo=?, campos_visiveis=?,
           sla_horas=?, checklist_padrao=?, template_descricao=?, requer_aprovacao=?,
           valor_aprovacao_limite=? WHERE id=?""",
        (nome, descricao, cor, 1 if ativo else 0, campos_visiveis,
         sla_horas, checklist_padrao, template_descricao,
         1 if requer_aprovacao else 0, valor_aprovacao_limite, category_id)
    )
    db.commit()

def create_category_full(nome: str, descricao: str = "", cor: str = "#6366f1",
                          campos_visiveis: str = None, sla_horas: int = None,
                          checklist_padrao: str = None, template_descricao: str = None,
                          requer_aprovacao: bool = False, valor_aprovacao_limite: float = None) -> int:
    db = get_db()
    cur = db.execute(
        """INSERT INTO categories (nome, descricao, cor, ativo, campos_visiveis, sla_horas,
           checklist_padrao, template_descricao, requer_aprovacao, valor_aprovacao_limite, criado_em)
           VALUES (?,?,?,1,?,?,?,?,?,?,?)""",
        (nome, descricao, cor, campos_visiveis, sla_horas,
         checklist_padrao, template_descricao,
         1 if requer_aprovacao else 0, valor_aprovacao_limite, _now())
    )
    db.commit()
    return cur.lastrowid

# ── Grupos de Operadores ──────────────────────────────────────────────────────

def list_groups():
    return get_db().execute(
        "SELECT * FROM operator_groups ORDER BY nome"
    ).fetchall()

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
           JOIN group_members gm ON gm.user_id=u.id
           WHERE gm.group_id=?""", (group_id,)
    ).fetchall()

def get_group_categories(group_id: int):
    return get_db().execute(
        """SELECT c.id, c.nome, c.cor FROM categories c
           JOIN group_categories gc ON gc.category_id=c.id
           WHERE gc.group_id=?""", (group_id,)
    ).fetchall()

def assign_ticket_to_group(ticket_id: int, group_id: int) -> Optional[dict]:
    """Atribui chamado ao membro do grupo com menos chamados abertos (round-robin simples)."""
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

# ── Webhooks ──────────────────────────────────────────────────────────────────

def list_webhooks():
    return get_db().execute("SELECT * FROM webhooks ORDER BY nome").fetchall()

def create_webhook(nome: str, url: str, eventos: list, secret: str = "") -> int:
    import json as _json
    db = get_db()
    cur = db.execute(
        "INSERT INTO webhooks (nome, url, eventos, ativo, secret, criado_em) VALUES (?,?,?,1,?,?)",
        (nome, url, _json.dumps(eventos), secret, _now())
    )
    db.commit()
    return cur.lastrowid

def update_webhook(webhook_id: int, nome: str, url: str, eventos: list, ativo: bool, secret: str = ""):
    import json as _json
    db = get_db()
    db.execute(
        "UPDATE webhooks SET nome=?, url=?, eventos=?, ativo=?, secret=? WHERE id=?",
        (nome, url, _json.dumps(eventos), 1 if ativo else 0, secret, webhook_id)
    )
    db.commit()

def delete_webhook(webhook_id: int):
    db = get_db().execute("DELETE FROM webhooks WHERE id=?", (webhook_id,))
    get_db().commit()

def fire_webhooks(evento: str, payload: dict):
    """Dispara webhooks ativos que escutam o evento."""
    import json as _json, hmac, hashlib, threading
    try:
        rows = get_db().execute(
            "SELECT * FROM webhooks WHERE ativo=1 AND eventos LIKE ?", (f"%{evento}%",)
        ).fetchall()
    except Exception:
        return
    for row in rows:
        try:
            evts = _json.loads(row["eventos"])
        except Exception:
            evts = []
        if evento not in evts:
            continue
        body = _json.dumps({"evento": evento, **payload}, default=str, ensure_ascii=False)
        def _send(url, body, secret):
            try:
                import urllib.request
                headers = {"Content-Type": "application/json"}
                if secret:
                    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
                    headers["X-CCTI-Signature"] = sig
                req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        threading.Thread(target=_send, args=(row["url"], body, row["secret"] or ""), daemon=True).start()

# ── Busca avançada ────────────────────────────────────────────────────────────

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
            sql += f" AND t.categoria_id IN ({','.join('?'*len(aids))})"; params.extend(aids)
    if q:
        like = f"%{q}%"
        sql += """ AND (t.titulo LIKE ? OR t.solicitante LIKE ? OR t.responsavel LIKE ?
                        OR t.numero_chamado LIKE ? OR t.descricao LIKE ?)"""
        params.extend([like, like, like, like, like])
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
