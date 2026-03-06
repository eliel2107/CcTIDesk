import os, uuid, csv, json
from .notify import notify_ticket_created, notify_ticket_assigned, notify_status_changed
from .models import list_tickets_paginated
from app.extensions import limiter
from io import StringIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, current_app, send_from_directory, abort, g
from werkzeug.utils import secure_filename

from .db import init_db, get_db
from .auth import login_required, role_required
from .address_book import DELIVERY_PRESETS, SENDER_PRESETS
from .services.asset_service import list_assets_for_select, get_asset

from .models import (
    STATUSES, TYPES, PRIORITIES,
    _today_ymd,
    create_ticket, list_tickets, get_ticket, update_status, update_fields, get_logs,
    dashboard_stats, dashboard_stats_advanced, list_attachments, add_attachment, count_attachments,
    list_steps, toggle_step, add_step, delete_step, move_step,
    delete_attachment,
    list_tickets_by_requester, list_queue_tickets, assign_ticket
)

bp = Blueprint("routes", __name__)

@bp.before_app_request
def ensure_db():
    try:
        init_db()
    except Exception:
        pass

def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]

def _solicitante_can_edit(ticket) -> bool:
    """Retorna True se o usuário atual pode editar o chamado.
    Solicitantes ficam bloqueados enquanto houver um responsável atribuído.
    Quando assigned_user_id for removido (None), o acesso é restaurado.
    """
    if g.user and g.user["role"] == "solicitante":
        if ticket and ticket["assigned_user_id"]:
            return False
    return True

@bp.get("/search")
@login_required
def global_search():
    q = (request.args.get("q") or "").strip()
    db = get_db()
    tickets = []
    assets = []
    if q:
        like = f"%{q}%"
        tickets = db.execute("""SELECT id, tipo, titulo, responsavel, prioridade, status, atualizado_em
                                FROM tickets
                                WHERE titulo LIKE ? OR solicitante LIKE ? OR responsavel LIKE ? OR codigo_rastreio LIKE ? OR descricao LIKE ?
                                ORDER BY atualizado_em DESC LIMIT 20""", (like, like, like, like, like)).fetchall()
        assets = db.execute("""SELECT id, tag, tipo, modelo, serial_number, local_base, responsavel, status, atualizado_em
                               FROM assets
                               WHERE tag LIKE ? OR modelo LIKE ? OR serial_number LIKE ? OR local_base LIKE ? OR responsavel LIKE ?
                               ORDER BY atualizado_em DESC LIMIT 20""", (like, like, like, like, like)).fetchall()
    return render_template("search.html", q=q, tickets=tickets, assets=assets)


@bp.get("/novo-chamado")
@login_required
@role_required('solicitante')
def requester_new_ticket():
    return render_template("requester_new_ticket.html", TYPES=TYPES, PRIORITIES=PRIORITIES)

@bp.post("/novo-chamado")
@login_required
@role_required('solicitante')
@limiter.limit("20 per hour", error_message="Limite de chamados atingido. Aguarde antes de abrir mais chamados.")
def requester_create_ticket():
    try:
        data = dict(request.form)
        data["requester_user_id"] = g.user["id"]
        data["solicitante"] = g.user["nome"]
        tid = create_ticket(data)
        notify_ticket_created(
            current_app.config,
            ticket_id=tid,
            titulo=data.get("titulo",""),
            solicitante=g.user["nome"],
            tipo=data.get("tipo",""),
        )
        flash(f"Chamado criado com ID {tid}.", "success")
        return redirect(url_for("routes.my_tickets"))
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("routes.requester_new_ticket"))

@bp.get("/meus-chamados")
@login_required
@role_required('solicitante')
def my_tickets():
    tickets = list_tickets_by_requester(g.user["id"])
    return render_template("my_tickets.html", tickets=tickets, stats_today=_today_ymd())

@bp.get("/fila")
@login_required
@role_required('admin', 'operador')
def queue():
    filters = {k: request.args.get(k, "") for k in ["status","tipo","q","only_unassigned"]}
    tickets = list_queue_tickets(filters)
    return render_template("queue.html", tickets=tickets, STATUSES=STATUSES, TYPES=TYPES, filters=filters)

@bp.post("/fila/<int:ticket_id>/assumir")
@login_required
@role_required('admin', 'operador')
def take_ticket(ticket_id: int):
    try:
        assign_ticket(ticket_id, g.user["id"], g.user["nome"])
        _t = get_ticket(ticket_id)
        if _t:
            from .services.auth_service import get_user
            _req = get_user(_t["requester_user_id"]) if _t["requester_user_id"] else None
            notify_ticket_assigned(
                current_app.config,
                ticket_id=ticket_id,
                titulo=_t["titulo"],
                responsavel=g.user["nome"],
                requester_email=_req["email"] if _req else None,
            )
        flash("Chamado assumido com sucesso.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.queue"))

@bp.get("/api/address-book")

@login_required
def api_address_book():
    return {"delivery": DELIVERY_PRESETS, "sender": SENDER_PRESETS}

@bp.get("/dashboard")
@login_required
def dashboard():
    if g.user and g.user["role"] == "solicitante":
        return redirect(url_for("routes.my_tickets"))
    stats = dashboard_stats_advanced()
    return render_template("dashboard.html", stats=stats, STATUSES=STATUSES)

@bp.get("/home")
@login_required
def executive_home():
    db = get_db()
    open_count = db.execute("SELECT COUNT(*) as c FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO')").fetchone()["c"]
    overdue_count = db.execute("SELECT COUNT(*) as c FROM tickets WHERE data_limite IS NOT NULL AND data_limite < date('now') AND status NOT IN ('CONCLUIDO','CANCELADO')").fetchone()["c"]
    asset_total = db.execute("SELECT COUNT(*) as c FROM assets").fetchone()["c"] if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'").fetchone() else 0
    assets_in_transit = db.execute("SELECT COUNT(*) as c FROM assets WHERE status='EM_TRANSITO'").fetchone()["c"] if asset_total >= 0 else 0
    assets_without_owner = db.execute("SELECT COUNT(*) as c FROM assets WHERE COALESCE(TRIM(responsavel),'')=''").fetchone()["c"] if asset_total >= 0 else 0
    return render_template("home_exec.html", open_count=open_count, overdue_count=overdue_count, asset_total=asset_total, assets_in_transit=assets_in_transit, assets_without_owner=assets_without_owner)

@bp.get("/")
@login_required
def index():

    filters = {k: request.args.get(k, "") for k in ["status","tipo","prioridade","responsavel","q","sort_by","asset_id"]}
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 25
    tickets, total, total_pages = list_tickets_paginated(filters, page=page, per_page=per_page)
    stats_today = _today_ymd()
    return render_template(
        "index.html",
        tickets=tickets, STATUSES=STATUSES, TYPES=TYPES, PRIORITIES=PRIORITIES,
        filters=filters, stats_today=stats_today,
        page=page, total=total, total_pages=total_pages, per_page=per_page,
    )

@bp.get("/tickets/new")
@login_required
@role_required('admin', 'operador')
def new_ticket():
    return render_template("new_ticket.html", TYPES=TYPES, PRIORITIES=PRIORITIES, assets=list_assets_for_select())

@bp.post("/tickets")
@login_required
@role_required('admin', 'operador')
@limiter.limit("60 per hour", error_message="Limite de criação de chamados atingido.")
def create_ticket_route():
    try:
        data2 = dict(request.form)
        tid = create_ticket(data2)
        notify_ticket_created(
            current_app.config,
            ticket_id=tid,
            titulo=data2.get("titulo",""),
            solicitante=data2.get("solicitante", g.user["nome"]),
            tipo=data2.get("tipo",""),
        )
        flash(f"Chamado criado com ID {tid}.", "success")
        return redirect(url_for("routes.ticket_detail", ticket_id=tid))
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("routes.new_ticket"))

@bp.get("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id: int):
    t = get_ticket(ticket_id)
    if g.user and g.user["role"] == "solicitante" and t and t["requester_user_id"] != g.user["id"]:
        flash("Você não tem permissão para acessar este chamado.", "error")
        return redirect(url_for("routes.my_tickets"))
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    logs = get_logs(ticket_id)
    attachments = list_attachments(ticket_id)
    steps = list_steps(ticket_id)
    max_files = current_app.config["MAX_ATTACHMENTS_PER_TYPE"].get(t["tipo"], 20)
    allowed = ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"]))
    asset = get_asset(t["asset_id"]) if "asset_id" in t.keys() and t["asset_id"] else None
    return render_template(
        "ticket_detail.html",
        ticket=t,
        asset=asset,
        logs=logs,
        attachments=attachments,
        steps=steps,
        STATUSES=STATUSES,
        max_files=max_files,
        allowed_ext=allowed,
        assets=list_assets_for_select()
    )

@bp.post("/tickets/<int:ticket_id>/status")
@login_required
@role_required('admin', 'operador')
def update_status_route(ticket_id: int):
    try:
        new_st = request.form.get("status","")
        update_status(ticket_id, new_st, request.form.get("detalhe",""))
        _t = get_ticket(ticket_id)
        if _t:
            from .services.auth_service import get_user
            _req = get_user(_t["requester_user_id"]) if _t["requester_user_id"] else None
            notify_status_changed(
                current_app.config,
                ticket_id=ticket_id,
                titulo=_t["titulo"],
                new_status=new_st,
                requester_email=_req["email"] if _req else None,
            )
        flash("Status atualizado.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/edit")
@login_required
@role_required('admin', 'operador')
def edit_ticket_route(ticket_id: int):
    try:
        update_fields(ticket_id, dict(request.form))
        flash("Chamado atualizado.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/steps/<int:step_id>/toggle")
@login_required
@role_required('admin', 'operador')
def toggle_step_route(ticket_id: int, step_id: int):
    done = request.form.get("done") == "on"
    try:
        toggle_step(step_id, done)
        flash("Etapa atualizada.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/steps/add")
@login_required
@role_required('admin', 'operador')
def add_step_route(ticket_id: int):
    text = request.form.get("text", "")
    position = request.form.get("position", "end")
    ref_step_id = request.form.get("ref_step_id")
    try:
        add_step(ticket_id, text, position=position, ref_step_id=int(ref_step_id) if ref_step_id else None)
        flash("Etapa adicionada.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/steps/<int:step_id>/delete")
@login_required
@role_required('admin', 'operador')
def delete_step_route(ticket_id: int, step_id: int):
    try:
        delete_step(ticket_id, step_id)
        flash("Etapa removida.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/steps/<int:step_id>/move")
@login_required
@role_required('admin', 'operador')
def move_step_route(ticket_id: int, step_id: int):
    direction = request.form.get("direction", "")
    try:
        move_step(ticket_id, step_id, direction)
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/upload")
@login_required
def upload_attachment(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))

    # Solicitante só pode enviar anexos enquanto ninguém assumiu o chamado
    if not _solicitante_can_edit(t):
        flash("Este chamado já está em atendimento. Você não pode enviar anexos enquanto há um responsável atribuído.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

    # Operador/admin podem sempre — mas solicitante só acessa o próprio chamado
    if g.user["role"] == "solicitante" and t["requester_user_id"] != g.user["id"]:
        flash("Você não tem permissão para enviar anexos neste chamado.", "error")
        return redirect(url_for("routes.my_tickets"))

    files = request.files.getlist("files")
    files = [f for f in files if f and (f.filename or "").strip() != ""]
    if not files:
        flash("Selecione pelo menos um arquivo.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

    max_files = current_app.config["MAX_ATTACHMENTS_PER_TYPE"].get(t["tipo"], 20)
    current = count_attachments(ticket_id)
    if current + len(files) > max_files:
        flash(f"Limite de anexos excedido: {current}/{max_files} já anexados. Você tentou enviar {len(files)}.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(ticket_id))
    os.makedirs(folder, exist_ok=True)

    allowed_list = ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"]))
    saved = 0

    for file in files:
        original = secure_filename(file.filename)
        if not _allowed_file(original):
            flash(f"Arquivo bloqueado: {original}. Permitidos: {allowed_list}.", "error")
            continue

        ext = os.path.splitext(original)[1].lower()
        stored = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(folder, stored)
        file.save(save_path)

        add_attachment(ticket_id, stored, original, file.mimetype or "", os.path.getsize(save_path))
        saved += 1

    if saved:
        flash(f"{saved} anexo(s) enviado(s).", "success")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.post("/tickets/<int:ticket_id>/files/<int:attachment_id>/delete")
@login_required
def delete_attachment_route(ticket_id: int, attachment_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    # Solicitante não pode excluir anexos quando chamado está em atendimento
    if g.user["role"] == "solicitante":
        if not _solicitante_can_edit(t):
            flash("Não é possível excluir anexos enquanto o chamado está em atendimento.", "error")
            return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
        if t["requester_user_id"] != g.user["id"]:
            flash("Você não tem permissão para excluir anexos neste chamado.", "error")
            return redirect(url_for("routes.my_tickets"))
    try:
        stored = delete_attachment(ticket_id, attachment_id)
        # remove do disco
        folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(ticket_id))
        path = os.path.join(folder, stored)
        if os.path.exists(path):
            os.remove(path)
        flash("Anexo removido.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))

@bp.get("/tickets/<int:ticket_id>/files/<int:attachment_id>")
@login_required
def download_attachment(ticket_id: int, attachment_id: int):
    row = get_db().execute(
        "SELECT stored_name, original_name FROM attachments WHERE id=? AND ticket_id=?",
        (attachment_id, ticket_id)
    ).fetchone()
    if not row:
        abort(404)
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(ticket_id))
    return send_from_directory(folder, row["stored_name"], as_attachment=True, download_name=row["original_name"])


@bp.get("/kanban")
@login_required
def kanban():
    # Mostra apenas não concluídos/cancelados por padrão
    db = get_db()
    stats_today = _today_ymd()

    # Defina as colunas que fazem sentido pro fluxo
    statuses = [
        ("ABERTO", "Aberto"),
        ("EM_ANDAMENTO", "Em andamento"),
        ("AGUARDANDO_FORNECEDOR", "Aguardando fornecedor"),
        ("AGUARDANDO_APROVACAO", "Aguardando aprovação"),
        ("ENVIADO", "Enviado"),
        ("CONCLUIDO", "Concluído"),
        ("CANCELADO", "Cancelado"),
    ]

    rows = db.execute("""SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite, atualizado_em
                           FROM tickets
                           ORDER BY atualizado_em DESC""").fetchall()

    by_status = {s[0]: [] for s in statuses}
    for t in rows:
        st = t["status"]
        if st not in by_status:
            by_status.setdefault(st, []).append(t)
        else:
            by_status[st].append(t)

    columns = [{"status": s, "title": title, "cards": by_status.get(s, [])} for s, title in statuses]
    return render_template("kanban.html", columns=columns, stats_today=stats_today)


@bp.get("/export.csv")
@login_required
def export_csv():
    filters = {k: request.args.get(k, "") for k in ["status","tipo","prioridade","responsavel","q","sort_by","asset_id"]}
    tickets = list_tickets(filters)
    si = StringIO()
    w = csv.writer(si)
    w.writerow(["id","tipo","titulo","solicitante","responsavel","prioridade","status","data_limite","atualizado_em"])
    for r in tickets:
        w.writerow([r["id"],r["tipo"],r["titulo"],r["solicitante"],r["responsavel"],r["prioridade"],r["status"],r["data_limite"],r["atualizado_em"]])
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment; filename=chamados_export.csv"})
