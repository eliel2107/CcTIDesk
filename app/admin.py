from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.auth import login_required, role_required
from app.services.user_service import list_users, create_user, update_user, set_user_active, get_user_by_id, delete_user, ROLES

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/users")
@login_required
@role_required("admin")
def users():
    return render_template("admin_users.html", users=list_users(), roles=ROLES)

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
