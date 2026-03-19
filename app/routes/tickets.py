"""Rotas de Chamados — CRUD, detalhes, upload, etapas."""

import os, uuid, json
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort, g, jsonify
from werkzeug.utils import secure_filename

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.extensions import limiter
from app.db import get_db
from app.constants import STATUSES, TYPES, PRIORITIES, CLASSIFICATIONS, QUEUE_VISIBLE_STATUSES
from app.helpers import _today_ymd
from app.services.ticket_service import (
    create_ticket, get_ticket, update_status, update_fields, get_logs,
    list_attachments, add_attachment, count_attachments, delete_attachment,
    list_steps, toggle_step, add_step, delete_step, move_step,
    list_tickets_by_requester, assign_ticket,
)
from app.services.sla_service import get_sla_status
from app.services.comment_service import get_comments
from app.services.workflow_service import get_transfers
from app.services.group_service import list_groups
from app.services.category_service import list_categories, get_category, get_user_categories
from app.services.asset_service import list_assets_for_select, get_asset
from app.services.search_service import search_tickets_advanced
from app.notifications import (
    on_ticket_criado, on_ticket_assumido, on_status_atualizado,
    on_aprovacao_necessaria,
)
from app.notify import notify_ticket_created, notify_ticket_assigned, notify_status_changed
from app import ai_service
from app.services.ai.gemini_client import GeminiClientError


def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _solicitante_can_edit(ticket) -> bool:
    if g.user and g.user["role"] == "solicitante":
        if ticket and ticket["assigned_user_id"]:
            return False
    return True


# ── Solicitante ──────────────────────────────────────────────────────────

@bp.get("/novo-chamado")
@login_required
@role_required('solicitante')
def requester_new_ticket():
    categories = list_categories(only_active=True)
    cat_id = request.args.get("cat", "")
    selected_cat = None
    if cat_id:
        try:
            selected_cat = next((c for c in categories if str(c["id"]) == cat_id), None)
        except Exception:
            pass
    classif = request.args.get("classif", "REQUISICAO")
    if not cat_id or not selected_cat:
        return render_template("ticket_category_picker.html", categories=categories, next_url=url_for("routes.requester_new_ticket"))
    campos = []
    try:
        campos = json.loads(selected_cat["campos_visiveis"] or "[]")
    except Exception:
        pass
    return render_template("requester_new_ticket.html", TYPES=TYPES, PRIORITIES=PRIORITIES, CLASSIFICATIONS=CLASSIFICATIONS,
                           categories=categories, selected_cat=selected_cat, campos_visiveis=campos, classif=classif,
                           ai_enabled=current_app.config.get("AI_ASSIST_ENABLED", False))


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
        _t = get_ticket(tid)
        notify_ticket_created(current_app.config, ticket_id=tid, titulo=data.get("titulo", ""),
                              solicitante=g.user["nome"], tipo=data.get("tipo", ""))
        on_ticket_criado(tid, data.get("titulo", ""), _t["categoria_id"] if _t else None, g.user["id"])
        if _t and _t["status"] == "AGUARDANDO_APROVACAO":
            on_aprovacao_necessaria(tid, data.get("titulo", ""))
            flash("Chamado criado e aguardando aprovação de um admin.", "info")
        else:
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


# ── Operador / Admin ─────────────────────────────────────────────────────

@bp.get("/tickets/new")
@login_required
@role_required('admin', 'operador')
def new_ticket():
    categories = list_categories(only_active=True)
    cat_id = request.args.get("cat", "")
    selected_cat = None
    if cat_id:
        try:
            selected_cat = next((c for c in categories if str(c["id"]) == cat_id), None)
        except Exception:
            pass
    classif = request.args.get("classif", "REQUISICAO")
    if not cat_id or not selected_cat:
        return render_template("ticket_category_picker.html", categories=categories, next_url=url_for("routes.new_ticket"))
    campos = []
    try:
        campos = json.loads(selected_cat["campos_visiveis"] or "[]")
    except Exception:
        pass
    return render_template("new_ticket.html", TYPES=TYPES, PRIORITIES=PRIORITIES, CLASSIFICATIONS=CLASSIFICATIONS,
                           assets=list_assets_for_select(), categories=categories,
                           selected_cat=selected_cat, campos_visiveis=campos, classif=classif)


@bp.post("/tickets")
@login_required
@role_required('admin', 'operador')
@limiter.limit("60 per hour", error_message="Limite de criação de chamados atingido.")
def create_ticket_route():
    try:
        data2 = dict(request.form)
        if not data2.get("requester_user_id"):
            data2["requester_user_id"] = str(g.user["id"])
        tid = create_ticket(data2)
        _t = get_ticket(tid)
        notify_ticket_created(current_app.config, ticket_id=tid, titulo=data2.get("titulo", ""),
                              solicitante=data2.get("solicitante", g.user["nome"]), tipo=data2.get("tipo", ""))
        on_ticket_criado(tid, data2.get("titulo", ""), _t["categoria_id"] if _t else None, g.user["id"])
        if _t and _t["status"] == "AGUARDANDO_APROVACAO":
            on_aprovacao_necessaria(tid, data2.get("titulo", ""))
            flash("Chamado criado e aguardando aprovação.", "info")
        else:
            flash(f"Chamado criado com ID {tid}.", "success")
        return redirect(url_for("routes.ticket_detail", ticket_id=tid))
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("routes.new_ticket"))


@bp.get("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    # Verifica acesso: solicitantes só podem ver seus próprios chamados.
    if g.user["role"] == "solicitante" and t["requester_user_id"] != g.user["id"]:
        flash("Você não tem permissão para acessar este chamado.", "error")
        return redirect(url_for("routes.my_tickets"))
    logs = get_logs(ticket_id)
    attachments = list_attachments(ticket_id)
    steps = list_steps(ticket_id)
    comments = get_comments(ticket_id, include_internal=(g.user["role"] in ("admin", "operador")))
    transfers = get_transfers(ticket_id)
    max_files = current_app.config["MAX_ATTACHMENTS_PER_TYPE"].get(t["tipo"], 20)
    allowed = ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"]))
    asset = get_asset(t["asset_id"]) if "asset_id" in t.keys() and t["asset_id"] else None
    categoria = get_category(t["categoria_id"]) if t["categoria_id"] else None
    sla_status = get_sla_status(t)
    operators = []
    if g.user["role"] in ("admin", "operador"):
        db = get_db()
        operators = db.execute(
            "SELECT id, nome FROM users WHERE active=1 AND role IN ('admin','operador') AND id!=? ORDER BY nome",
            (g.user["id"],)
        ).fetchall()
    groups = list_groups() if g.user["role"] in ("admin", "operador") else []
    from app.kb import suggest_articles
    from app.services.stock_service import consumos_por_ticket, produtos_para_select
    kb_articles = suggest_articles(t["titulo"], t["categoria_id"]) if t["titulo"] else []
    consumos_ticket = consumos_por_ticket(ticket_id)
    produtos_estoque = produtos_para_select() if g.user["role"] in ("admin", "operador") else []
    return render_template(
        "ticket_detail.html",
        ticket=t, asset=asset, categoria=categoria, logs=logs,
        attachments=attachments, steps=steps, comments=comments, transfers=transfers,
        sla_status=sla_status, operators=operators, groups=groups,
        kb_articles=kb_articles, consumos_ticket=consumos_ticket,
        produtos_estoque=produtos_estoque, STATUSES=STATUSES,
        max_files=max_files, allowed_ext=allowed, assets=list_assets_for_select(),
        latest_ai_insight=ai_service.last_ticket_insight(ticket_id),
        ai_enabled=current_app.config.get("AI_ASSIST_ENABLED", False)
    )


@bp.post("/tickets/<int:ticket_id>/status")
@login_required
@role_required('admin', 'operador')
def update_status_route(ticket_id: int):
    try:
        new_st = request.form.get("status", "")
        t_before = get_ticket(ticket_id)
        if not t_before:
            flash("Chamado não encontrado.", "error")
            return redirect(url_for("routes.index"))
        if g.user["role"] != "admin":
            if t_before["status"] == "AGUARDANDO_APROVACAO":
                flash("Chamados em aprovação não podem ter o status alterado diretamente.", "error")
                return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
            if new_st == "AGUARDANDO_APROVACAO":
                flash("Apenas administradores podem colocar um chamado em aprovação.", "error")
                return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
        update_status(ticket_id, new_st, request.form.get("detalhe", ""))
        _t = get_ticket(ticket_id)
        if _t:
            from app.services.auth_service import get_user
            _req = get_user(_t["requester_user_id"]) if _t["requester_user_id"] else None
            notify_status_changed(current_app.config, ticket_id=ticket_id, titulo=_t["titulo"],
                                  new_status=new_st, requester_email=_req["email"] if _req else None)
            if _t["requester_user_id"]:
                on_status_atualizado(ticket_id, _t["titulo"], _t["requester_user_id"], new_st)
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


# ── Etapas ───────────────────────────────────────────────────────────────

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


# ── Upload / Anexos ──────────────────────────────────────────────────────

@bp.post("/tickets/<int:ticket_id>/upload")
@login_required
def upload_attachment(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        flash("Chamado não encontrado.", "error")
        return redirect(url_for("routes.index"))
    if not _solicitante_can_edit(t):
        flash("Este chamado já está em atendimento. Você não pode enviar anexos.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
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
        flash(f"Limite de anexos excedido: {current}/{max_files}.", "error")
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
    if g.user["role"] == "solicitante":
        if not _solicitante_can_edit(t):
            flash("Não é possível excluir anexos enquanto o chamado está em atendimento.", "error")
            return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
        if t["requester_user_id"] != g.user["id"]:
            flash("Sem permissão.", "error")
            return redirect(url_for("routes.my_tickets"))
    try:
        stored = delete_attachment(ticket_id, attachment_id)
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
