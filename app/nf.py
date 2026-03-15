from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
from app.auth import login_required, role_required
from app.services.nf_service import (
    list_entradas, get_entrada, get_itens, get_assets_gerados,
    criar_entrada, atualizar_entrada, adicionar_item, remover_item,
    gerar_preview, confirmar_entrada, cancelar_entrada, delete_entrada_admin,
    TIPOS_ATIVO, TIPOS_CONSUMIVEL, TIPO_LABEL,
    STATUS_RASCUNHO, STATUS_CONFIRMADA,
)

bp = Blueprint("nf", __name__, url_prefix="/nf")

TODOS_TIPOS = TIPOS_ATIVO + TIPOS_CONSUMIVEL


# ── Lista de NFs ──────────────────────────────────────────────────────
@bp.get("/")
@login_required
@role_required("admin", "operador")
def nf_list():
    filtros = {k: request.args.get(k, "") for k in ["q", "status"]}
    return render_template(
        "nf/list.html",
        entradas=list_entradas(filtros),
        filtros=filtros,
    )


# ── Nova NF (cabeçalho) ───────────────────────────────────────────────
@bp.get("/nova")
@login_required
@role_required("admin", "operador")
def nf_nova():
    return render_template("nf/form_cabecalho.html", entrada=None)


@bp.post("/nova")
@login_required
@role_required("admin", "operador")
def nf_criar():
    try:
        data = dict(request.form)
        data["usuario"] = g.user["nome"]
        eid = criar_entrada(data)
        flash("NF criada. Adicione os itens abaixo.", "success")
        return redirect(url_for("nf.nf_itens", eid=eid))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("nf.nf_nova"))


# ── Editar cabeçalho ──────────────────────────────────────────────────
@bp.get("/<int:eid>/editar")
@login_required
@role_required("admin", "operador")
def nf_editar(eid: int):
    e = get_entrada(eid)
    if not e or e["status"] != STATUS_RASCUNHO:
        flash("NF não encontrada ou já confirmada.", "error")
        return redirect(url_for("nf.nf_list"))
    return render_template("nf/form_cabecalho.html", entrada=e)


@bp.post("/<int:eid>/editar")
@login_required
@role_required("admin", "operador")
def nf_editar_post(eid: int):
    try:
        atualizar_entrada(eid, dict(request.form))
        flash("NF atualizada.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("nf.nf_itens", eid=eid))


# ── Gestão de itens (passo 2) ─────────────────────────────────────────
@bp.get("/<int:eid>/itens")
@login_required
@role_required("admin", "operador")
def nf_itens(eid: int):
    e = get_entrada(eid)
    if not e:
        flash("NF não encontrada.", "error")
        return redirect(url_for("nf.nf_list"))
    from app.services.catalogo_service import list_catalogo
    return render_template(
        "nf/itens.html",
        entrada=e,
        itens=get_itens(eid),
        catalogo=list_catalogo(),
        TODOS_TIPOS=TODOS_TIPOS,
        TIPOS_ATIVO=TIPOS_ATIVO,
        TIPO_LABEL=TIPO_LABEL,
    )


@bp.post("/<int:eid>/itens/add")
@login_required
@role_required("admin", "operador")
def nf_add_item(eid: int):
    try:
        adicionar_item(eid, dict(request.form))
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("nf.nf_itens", eid=eid))


@bp.post("/<int:eid>/itens/<int:iid>/remover")
@login_required
@role_required("admin", "operador")
def nf_remover_item(eid: int, iid: int):
    remover_item(iid, eid)
    return redirect(url_for("nf.nf_itens", eid=eid))


# ── Preview + confirmação (passo 3) ───────────────────────────────────
@bp.get("/<int:eid>/preview")
@login_required
@role_required("admin", "operador")
def nf_preview(eid: int):
    e = get_entrada(eid)
    if not e or e["status"] != STATUS_RASCUNHO:
        flash("NF não disponível para preview.", "error")
        return redirect(url_for("nf.nf_list"))
    itens = get_itens(eid)
    if not itens:
        flash("Adicione ao menos um item antes de continuar.", "error")
        return redirect(url_for("nf.nf_itens", eid=eid))
    try:
        preview = gerar_preview(eid)
    except ValueError as ex:
        flash(str(ex), "error")
        return redirect(url_for("nf.nf_itens", eid=eid))
    return render_template(
        "nf/preview.html",
        entrada=e,
        preview=preview,
        TIPO_LABEL=TIPO_LABEL,
    )


@bp.post("/<int:eid>/confirmar")
@login_required
@role_required("admin", "operador")
def nf_confirmar(eid: int):
    try:
        resultado = confirmar_entrada(eid, dict(request.form), g.user["nome"])
        n_at = len(resultado["assets"])
        n_st = len(resultado["stock"])
        flash(
            f"NF confirmada! {n_at} ativo(s) criado(s)"
            + (f" e {n_st} item(ns) de estoque atualizado(s)." if n_st else "."),
            "success"
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("nf.nf_preview", eid=eid))
    return redirect(url_for("nf.nf_detail", eid=eid))


# ── Detalhe (pós-confirmação) ─────────────────────────────────────────
@bp.get("/<int:eid>")
@login_required
@role_required("admin", "operador")
def nf_detail(eid: int):
    e = get_entrada(eid)
    if not e:
        flash("NF não encontrada.", "error")
        return redirect(url_for("nf.nf_list"))
    return render_template(
        "nf/detail.html",
        entrada=e,
        itens=get_itens(eid),
        assets_gerados=get_assets_gerados(eid),
        TIPO_LABEL=TIPO_LABEL,
        STATUS_CONFIRMADA=STATUS_CONFIRMADA,
    )


# ── Cancelar ──────────────────────────────────────────────────────────
@bp.post("/<int:eid>/cancelar")
@login_required
@role_required("admin", "operador")
def nf_cancelar(eid: int):
    cancelar_entrada(eid, current_app.config.get("NF_CANCELLED_DRAFT_RETENTION_DAYS", 15))
    flash("Entrada cancelada.", "success")
    return redirect(url_for("nf.nf_list"))

@bp.post("/<int:eid>/itens/add-catalogo")
@login_required
@role_required("admin", "operador")
def nf_add_items_catalogo(eid: int):
    """Adiciona múltiplos itens do catálogo de uma vez."""
    ids = request.form.getlist("catalogo_ids")
    erros = []
    for cid in ids:
        try:
            qtd_key = f"qtd_{cid}"
            adicionar_item(eid, {
                "catalogo_id": cid,
                "quantidade": request.form.get(qtd_key, 1),
            })
        except ValueError as e:
            erros.append(str(e))
    if erros:
        flash(" | ".join(erros), "error")
    elif ids:
        flash(f"{len(ids)} item(ns) adicionado(s).", "success")
    return redirect(url_for("nf.nf_itens", eid=eid))


@bp.post("/<int:eid>/excluir")
@login_required
@role_required("admin")
def nf_excluir(eid: int):
    try:
        delete_entrada_admin(eid)
        flash("NF excluída com sucesso.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("nf.nf_list"))
