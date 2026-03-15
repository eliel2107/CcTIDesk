from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.auth import login_required, role_required
from app.services.catalogo_service import (
    list_catalogo, get_produto_catalogo,
    criar_produto_catalogo, atualizar_produto_catalogo, deletar_produto_catalogo,
    TODOS_TIPOS,
)
from app.services.nf_service import TIPO_LABEL, TIPOS_ATIVO

bp = Blueprint("catalogo", __name__, url_prefix="/catalogo")


@bp.get("/")
@login_required
@role_required("admin", "operador")
def catalogo_list():
    filtros = {k: request.args.get(k, "") for k in ["q", "tipo_item"]}
    inativos = request.args.get("inativos") == "1"
    return render_template(
        "catalogo/list.html",
        produtos=list_catalogo(filtros, apenas_ativos=not inativos),
        filtros=filtros,
        inativos=inativos,
        TODOS_TIPOS=TODOS_TIPOS,
        TIPO_LABEL=TIPO_LABEL,
        TIPOS_ATIVO=TIPOS_ATIVO,
    )


@bp.get("/novo")
@login_required
@role_required("admin", "operador")
def catalogo_novo():
    return render_template(
        "catalogo/form.html", produto=None,
        TODOS_TIPOS=TODOS_TIPOS, TIPO_LABEL=TIPO_LABEL, TIPOS_ATIVO=TIPOS_ATIVO,
    )


@bp.post("/novo")
@login_required
@role_required("admin", "operador")
def catalogo_criar():
    try:
        criar_produto_catalogo(dict(request.form))
        flash("Produto cadastrado no catálogo.", "success")
        return redirect(url_for("catalogo.catalogo_list"))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("catalogo.catalogo_novo"))


@bp.get("/<int:pid>/editar")
@login_required
@role_required("admin", "operador")
def catalogo_editar(pid: int):
    p = get_produto_catalogo(pid)
    if not p:
        flash("Produto não encontrado.", "error")
        return redirect(url_for("catalogo.catalogo_list"))
    return render_template(
        "catalogo/form.html", produto=p,
        TODOS_TIPOS=TODOS_TIPOS, TIPO_LABEL=TIPO_LABEL, TIPOS_ATIVO=TIPOS_ATIVO,
    )


@bp.post("/<int:pid>/editar")
@login_required
@role_required("admin", "operador")
def catalogo_salvar(pid: int):
    try:
        atualizar_produto_catalogo(pid, dict(request.form))
        flash("Produto atualizado.", "success")
        return redirect(url_for("catalogo.catalogo_list"))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("catalogo.catalogo_editar", pid=pid))


@bp.post("/<int:pid>/deletar")
@login_required
@role_required("admin")
def catalogo_deletar(pid: int):
    deletar_produto_catalogo(pid)
    flash("Produto removido do catálogo.", "success")
    return redirect(url_for("catalogo.catalogo_list"))
