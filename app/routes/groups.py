"""Rotas de Grupos de Operadores."""

from flask import render_template, request, redirect, url_for, flash, g

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.services.group_service import (
    list_groups, get_group, create_group, update_group,
    set_group_members, set_group_categories, get_group_members, get_group_categories,
    assign_ticket_to_group,
)
from app.services.category_service import list_categories
from app.services.user_service import list_users


@bp.get("/grupos")
@login_required
@role_required("admin")
def groups_list():
    groups = list_groups()
    operators = [u for u in list_users() if u["role"] in ("admin", "operador")]
    categories = list_categories()
    group_members_map = {g_["id"]: get_group_members(g_["id"]) for g_ in groups}
    group_categories_map = {g_["id"]: get_group_categories(g_["id"]) for g_ in groups}
    return render_template("groups.html", groups=groups, operators=operators, categories=categories,
                           group_members_map=group_members_map, group_categories_map=group_categories_map)


@bp.post("/grupos/novo")
@login_required
@role_required("admin")
def create_group_route():
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Nome é obrigatório.", "error")
        return redirect(url_for("routes.groups_list"))
    gid = create_group(nome, request.form.get("descricao", ""), request.form.get("cor", "#6366f1"))
    member_ids = [int(i) for i in request.form.getlist("member_ids") if str(i).isdigit()]
    category_ids = [int(i) for i in request.form.getlist("category_ids") if str(i).isdigit()]
    if member_ids: set_group_members(gid, member_ids)
    if category_ids: set_group_categories(gid, category_ids)
    flash(f"Grupo '{nome}' criado.", "success")
    return redirect(url_for("routes.groups_list"))


@bp.post("/grupos/<int:group_id>/editar")
@login_required
@role_required("admin")
def edit_group_route(group_id: int):
    update_group(group_id, request.form.get("nome", ""), request.form.get("descricao", ""),
                 request.form.get("cor", "#6366f1"), request.form.get("ativo") == "1")
    member_ids = [int(i) for i in request.form.getlist("member_ids") if str(i).isdigit()]
    category_ids = [int(i) for i in request.form.getlist("category_ids") if str(i).isdigit()]
    set_group_members(group_id, member_ids)
    set_group_categories(group_id, category_ids)
    flash("Grupo atualizado.", "success")
    return redirect(url_for("routes.groups_list"))


@bp.post("/tickets/<int:ticket_id>/atribuir-grupo")
@login_required
@role_required("admin", "operador")
def assign_group_route(ticket_id: int):
    group_id = request.form.get("group_id", "")
    if not group_id or not group_id.isdigit():
        flash("Selecione um grupo.", "error")
        return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
    result = assign_ticket_to_group(ticket_id, int(group_id))
    if result:
        flash(f"Chamado atribuído a {result['nome']} (menor carga do grupo).", "success")
    else:
        flash("Grupo sem membros ativos.", "error")
    return redirect(url_for("routes.ticket_detail", ticket_id=ticket_id))
