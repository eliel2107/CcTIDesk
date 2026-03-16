"""Rotas de Busca e Exportação."""

import csv
from io import StringIO
from flask import render_template, request, redirect, url_for, flash, g, Response

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.db import get_db
from app.constants import STATUSES, CLASSIFICATIONS
from app.services.ticket_service import list_tickets
from app.services.search_service import search_tickets_advanced
from app.services.category_service import list_categories


@bp.get("/search")
@login_required
def global_search():
    q = (request.args.get("q") or "").strip()
    db = get_db()
    tickets = []
    assets = []
    if q:
        like = f"%{q}%"
        role = g.user["role"]
        uid = g.user["id"]
        if role == "solicitante":
            tickets = db.execute(
                """SELECT id, tipo, titulo, responsavel, prioridade, status, atualizado_em FROM tickets
                   WHERE requester_user_id=? AND (titulo LIKE ? OR solicitante LIKE ? OR responsavel LIKE ? OR codigo_rastreio LIKE ? OR descricao LIKE ?)
                   ORDER BY atualizado_em DESC LIMIT 20""", (uid, like, like, like, like, like)).fetchall()
        elif role == "operador":
            allowed = db.execute("SELECT category_id FROM user_categories WHERE user_id=?", (uid,)).fetchall()
            cat_ids = [r["category_id"] for r in allowed]
            if cat_ids:
                ph = ",".join("?" * len(cat_ids))
                tickets = db.execute(
                    f"""SELECT id, tipo, titulo, responsavel, prioridade, status, atualizado_em FROM tickets
                       WHERE categoria_id IN ({ph}) AND (titulo LIKE ? OR solicitante LIKE ? OR responsavel LIKE ? OR codigo_rastreio LIKE ? OR descricao LIKE ?)
                       ORDER BY atualizado_em DESC LIMIT 20""", cat_ids + [like, like, like, like, like]).fetchall()
            else:
                tickets = db.execute(
                    """SELECT id, tipo, titulo, responsavel, prioridade, status, atualizado_em FROM tickets
                       WHERE assigned_user_id=? AND (titulo LIKE ? OR solicitante LIKE ? OR responsavel LIKE ? OR codigo_rastreio LIKE ? OR descricao LIKE ?)
                       ORDER BY atualizado_em DESC LIMIT 20""", (uid, like, like, like, like, like)).fetchall()
        else:
            tickets = db.execute(
                """SELECT id, tipo, titulo, responsavel, prioridade, status, atualizado_em FROM tickets
                   WHERE titulo LIKE ? OR solicitante LIKE ? OR responsavel LIKE ? OR codigo_rastreio LIKE ? OR descricao LIKE ?
                   ORDER BY atualizado_em DESC LIMIT 20""", (like, like, like, like, like)).fetchall()
        if role in ("admin", "operador"):
            assets = db.execute(
                """SELECT id, tag, tipo, modelo, serial_number, local_base, responsavel, status, atualizado_em FROM assets
                   WHERE tag LIKE ? OR modelo LIKE ? OR serial_number LIKE ? OR local_base LIKE ? OR responsavel LIKE ?
                   ORDER BY atualizado_em DESC LIMIT 20""", (like, like, like, like, like)).fetchall()
    return render_template("search.html", q=q, tickets=tickets, assets=assets)


@bp.get("/busca-avancada")
@login_required
@role_required("admin", "operador")
def advanced_search():
    f = {k: request.args.get(k, "") for k in ["q", "status", "categoria_id", "classificacao", "responsavel", "data_inicio", "data_fim"]}
    results = []
    if any(f.values()):
        results = search_tickets_advanced(**f, user_id=g.user["id"], user_role=g.user["role"])
    categories = list_categories(only_active=True)
    return render_template("advanced_search.html", filters=f, results=results,
                           STATUSES=STATUSES, CLASSIFICATIONS=CLASSIFICATIONS, categories=categories)


@bp.get("/export.csv")
@login_required
@role_required('admin', 'operador')
def export_csv():
    filters = {k: request.args.get(k, "") for k in ["status", "tipo", "prioridade", "responsavel", "q", "sort_by", "asset_id"]}
    tickets = list_tickets(filters)
    si = StringIO()
    w = csv.writer(si)
    w.writerow(["id", "tipo", "titulo", "solicitante", "responsavel", "prioridade", "status", "data_limite", "atualizado_em"])
    for r in tickets:
        w.writerow([r["id"], r["tipo"], r["titulo"], r["solicitante"], r["responsavel"],
                     r["prioridade"], r["status"], r["data_limite"], r["atualizado_em"]])
    return Response(si.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=chamados_export.csv"})
