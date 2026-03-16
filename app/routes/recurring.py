"""Rotas de Chamados Recorrentes."""

import json as _json
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.db import get_db
from app.constants import PRIORITIES
from app.services.category_service import list_categories


@bp.get("/recorrentes")
@login_required
@role_required("admin")
def recurring_list():
    db = get_db()
    schedules = db.execute("SELECT * FROM recurring_tickets ORDER BY titulo").fetchall()
    categories = list_categories(only_active=True)
    return render_template("recurring.html", schedules=schedules, categories=categories, PRIORITIES=PRIORITIES)


@bp.post("/recorrentes/novo")
@login_required
@role_required("admin")
def recurring_create():
    titulo = request.form.get("titulo", "").strip()
    if not titulo:
        flash("Título é obrigatório.", "error")
        return redirect(url_for("routes.recurring_list"))
    ticket_data = {
        "descricao": request.form.get("descricao", ""),
        "prioridade": request.form.get("prioridade", "MEDIA"),
        "categoria_id": request.form.get("categoria_id", ""),
        "classificacao": request.form.get("classificacao", "REQUISICAO"),
    }
    db = get_db()
    db.execute(
        """INSERT INTO recurring_tickets (titulo, frequencia, dia_execucao, hora_execucao,
           ticket_data, ativo, criado_em) VALUES (?,?,?,?,?,1,?)""",
        (titulo, request.form.get("frequencia", "mensal"),
         request.form.get("dia_execucao") or None,
         request.form.get("hora_execucao", "08:00"),
         _json.dumps(ticket_data), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    flash(f"Chamado recorrente '{titulo}' criado.", "success")
    return redirect(url_for("routes.recurring_list"))


@bp.post("/recorrentes/<int:rid>/toggle")
@login_required
@role_required("admin")
def recurring_toggle(rid: int):
    db = get_db()
    row = db.execute("SELECT ativo FROM recurring_tickets WHERE id=?", (rid,)).fetchone()
    if row:
        db.execute("UPDATE recurring_tickets SET ativo=? WHERE id=?", (0 if row["ativo"] else 1, rid))
        db.commit()
    return redirect(url_for("routes.recurring_list"))


@bp.post("/recorrentes/<int:rid>/excluir")
@login_required
@role_required("admin")
def recurring_delete(rid: int):
    db = get_db()
    db.execute("DELETE FROM recurring_tickets WHERE id=?", (rid,))
    db.commit()
    flash("Agendamento removido.", "success")
    return redirect(url_for("routes.recurring_list"))
