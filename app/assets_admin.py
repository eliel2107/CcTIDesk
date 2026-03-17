from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.auth import login_required, role_required
from app.services.asset_service import (
    list_assets, get_asset, create_asset, update_asset, delete_asset,
    ASSET_TYPES, ASSET_STATUSES, tickets_by_asset, asset_dashboard, list_bases
)

bp = Blueprint("assets_admin", __name__, url_prefix="/assets")

@bp.get("/dashboard")
@login_required
def assets_dashboard():
    local_base = request.args.get("local_base", "")
    return render_template(
        "assets_dashboard.html",
        stats=asset_dashboard(local_base=local_base),
        bases=list_bases(),
        local_base=local_base,
    )

@bp.get("/")

@login_required
def assets():
    filters = {k: request.args.get(k, "") for k in ["q", "status", "tipo", "local_base"]}
    return render_template(
        "assets_list.html",
        assets=list_assets(filters),
        filters=filters,
        ASSET_TYPES=ASSET_TYPES,
        ASSET_STATUSES=ASSET_STATUSES,
        bases=list_bases(),
        stats=asset_dashboard(),
    )

@bp.get("/new")
@login_required
@role_required("admin", "operador")
def new_asset():
    return render_template("asset_form.html", asset=None, ASSET_TYPES=ASSET_TYPES, ASSET_STATUSES=ASSET_STATUSES)

@bp.post("/")
@login_required
@role_required("admin", "operador")
def create_asset_route():
    try:
        create_asset(dict(request.form))
        flash("Ativo criado com sucesso.", "success")
        return redirect(url_for("assets_admin.assets"))
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("assets_admin.new_asset"))

@bp.get("/<int:asset_id>")
@login_required
def asset_detail(asset_id: int):
    asset = get_asset(asset_id)
    if not asset:
        flash("Ativo não encontrado.", "error")
        return redirect(url_for("assets_admin.assets"))
    from app.services.asset_service import get_asset_history
    return render_template("asset_detail.html", asset=asset, tickets=tickets_by_asset(asset_id), history=get_asset_history(asset_id))

@bp.get("/<int:asset_id>/edit")
@login_required
@role_required("admin", "operador")
def edit_asset(asset_id: int):
    asset = get_asset(asset_id)
    if not asset:
        flash("Ativo não encontrado.", "error")
        return redirect(url_for("assets_admin.assets"))
    return render_template("asset_form.html", asset=asset, ASSET_TYPES=ASSET_TYPES, ASSET_STATUSES=ASSET_STATUSES)

@bp.post("/<int:asset_id>/edit")
@login_required
@role_required("admin", "operador")
def edit_asset_route(asset_id: int):
    try:
        update_asset(asset_id, dict(request.form))
        flash("Ativo atualizado.", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("assets_admin.asset_detail", asset_id=asset_id))
@bp.post("/<int:asset_id>/deletar")
@login_required
@role_required("admin")
def delete_asset_route(asset_id: int):
    asset = get_asset(asset_id)
    if not asset:
        flash("Ativo não encontrado.", "error")
        return redirect(url_for("assets_admin.assets"))
    tag = asset["tag"]
    delete_asset(asset_id)
    flash(f"Ativo {tag} excluído permanentemente.", "success")
    return redirect(url_for("assets_admin.assets"))
