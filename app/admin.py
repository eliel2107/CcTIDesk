from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.auth import login_required, role_required
from app.services.user_service import list_users, create_user, update_user, set_user_active, get_user_by_id, delete_user, ROLES
from app.models import (
    list_categories, get_category, create_category, update_category, delete_category,
    get_user_categories, set_user_categories,
    create_category_full, update_category_full,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

# ── Usuários ──────────────────────────────────────────────────────────────────

@bp.get("/users")
@login_required
@role_required("admin")
def users():
    all_categories = list_categories()
    users_list = list_users()
    user_cats = {u["id"]: get_user_categories(u["id"]) for u in users_list}
    return render_template("admin_users.html", users=users_list, roles=ROLES,
                           all_categories=all_categories, user_cats=user_cats)

@bp.post("/users")
@login_required
@role_required("admin")
def create_user_route():
    try:
        create_user(
            nome=request.form.get("nome",""),
            email=request.form.get("email",""),
            password=request.form.get("password",""),
            role=request.form.get("role","operador"),
            active=request.form.get("active") == "on",
        )
        flash("Usuário criado com sucesso.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))

@bp.post("/users/<int:user_id>/edit")
@login_required
@role_required("admin")
def edit_user_route(user_id: int):
    try:
        update_user(
            user_id=user_id,
            nome=request.form.get("nome",""),
            email=request.form.get("email",""),
            role=request.form.get("role","operador"),
            active=request.form.get("active") == "on",
        )
        flash("Usuário atualizado.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))

@bp.post("/users/<int:user_id>/toggle")
@login_required
@role_required("admin")
def toggle_user_route(user_id: int):
    row = get_user_by_id(user_id)
    if not row:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin.users"))
    try:
        set_user_active(user_id, not bool(row["active"]))
        flash("Status do usuário atualizado.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))

@bp.post("/users/<int:user_id>/delete")
@login_required
@role_required("admin")
def delete_user_route(user_id: int):
    try:
        delete_user(user_id, g.user["id"])
        flash("Usuário excluído com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))

@bp.post("/users/<int:user_id>/categories")
@login_required
@role_required("admin")
def set_user_categories_route(user_id: int):
    try:
        ids = [int(i) for i in request.form.getlist("category_ids") if str(i).isdigit()]
        set_user_categories(user_id, ids)
        flash("Categorias do usuário atualizadas.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))

# ── Categorias ────────────────────────────────────────────────────────────────

@bp.get("/categories")
@login_required
@role_required("admin")
def categories():
    cats = list_categories()
    return render_template("admin_categories.html", categories=cats)

@bp.post("/categories")
@login_required
@role_required("admin")
def create_category_route():
    try:
        campos = request.form.getlist("campos_visiveis")
        import json
        sla = request.form.get("sla_horas","").strip()
        vlim = request.form.get("valor_aprovacao_limite","").strip()
        checklist_raw = request.form.get("checklist_padrao","").strip()
        checklist = json.dumps([l for l in checklist_raw.splitlines() if l.strip()]) if checklist_raw else None
        create_category_full(
            nome=request.form.get("nome", ""),
            descricao=request.form.get("descricao", ""),
            cor=request.form.get("cor", "#6366f1"),
            campos_visiveis=json.dumps(campos) if campos else None,
            sla_horas=int(sla) if sla.isdigit() else None,
            checklist_padrao=checklist,
            template_descricao=request.form.get("template_descricao","").strip() or None,
            requer_aprovacao=request.form.get("requer_aprovacao") == "1",
            valor_aprovacao_limite=float(vlim) if vlim else None,
        )
        flash("Categoria criada com sucesso.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.categories"))

@bp.post("/categories/<int:category_id>/edit")
@login_required
@role_required("admin")
def edit_category_route(category_id: int):
    try:
        campos = request.form.getlist("campos_visiveis")
        import json
        sla = request.form.get("sla_horas","").strip()
        vlim = request.form.get("valor_aprovacao_limite","").strip()
        checklist_raw = request.form.get("checklist_padrao","").strip()
        checklist = json.dumps([l for l in checklist_raw.splitlines() if l.strip()]) if checklist_raw else None
        update_category_full(
            category_id=category_id,
            nome=request.form.get("nome", ""),
            descricao=request.form.get("descricao", ""),
            cor=request.form.get("cor", "#6366f1"),
            ativo=request.form.get("ativo") == "on",
            campos_visiveis=json.dumps(campos) if campos else None,
            sla_horas=int(sla) if sla.isdigit() else None,
            checklist_padrao=checklist,
            template_descricao=request.form.get("template_descricao","").strip() or None,
            requer_aprovacao=request.form.get("requer_aprovacao") == "1",
            valor_aprovacao_limite=float(vlim) if vlim else None,
        )
        flash("Categoria atualizada.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.categories"))

@bp.post("/categories/<int:category_id>/delete")
@login_required
@role_required("admin")
def delete_category_route(category_id: int):
    try:
        delete_category(category_id)
        flash("Categoria excluída.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("admin.categories"))
