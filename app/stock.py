from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from app.auth import login_required, role_required
from app.services.stock_service import (
    list_produtos, get_produto, create_produto, update_produto,
    registrar_movimentacao, get_movimentacoes, movimentacoes_recentes,
    consumos_por_ticket, produtos_para_select, stock_dashboard,
    CATEGORIAS, CATEGORIAS_LABEL, UNIDADES,
    TIPO_ENTRADA, TIPO_SAIDA, TIPO_AJUSTE,
)

bp = Blueprint("stock", __name__, url_prefix="/stock")


# ── Dashboard de estoque ──────────────────────────────────────────────
@bp.get("/")
@login_required
def stock_home():
    filtros = {k: request.args.get(k, "") for k in ["q", "categoria", "alerta"]}
    return render_template(
        "stock/index.html",
        produtos=list_produtos(filtros),
        filtros=filtros,
        dashboard=stock_dashboard(),
        CATEGORIAS=CATEGORIAS,
        CATEGORIAS_LABEL=CATEGORIAS_LABEL,
        movimentacoes=movimentacoes_recentes(10),
    )


# ── Novo produto ──────────────────────────────────────────────────────
@bp.get("/novo")
@login_required
@role_required("admin", "operador")
def novo_produto():
    return render_template(
        "stock/form.html",
        produto=None,
        CATEGORIAS=CATEGORIAS,
        CATEGORIAS_LABEL=CATEGORIAS_LABEL,
        UNIDADES=UNIDADES,
    )


@bp.post("/novo")
@login_required
@role_required("admin", "operador")
def criar_produto():
    try:
        data = dict(request.form)
        data["usuario"] = g.user["nome"]
        create_produto(data)
        flash("Produto criado no estoque.", "success")
        return redirect(url_for("stock.stock_home"))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("stock.novo_produto"))


# ── Detalhe + histórico ───────────────────────────────────────────────
@bp.get("/<int:pid>")
@login_required
def produto_detail(pid: int):
    p = get_produto(pid)
    if not p:
        flash("Produto não encontrado.", "error")
        return redirect(url_for("stock.stock_home"))
    return render_template(
        "stock/detail.html",
        produto=p,
        movimentacoes=get_movimentacoes(pid),
        TIPO_ENTRADA=TIPO_ENTRADA,
        TIPO_SAIDA=TIPO_SAIDA,
        TIPO_AJUSTE=TIPO_AJUSTE,
    )


# ── Editar produto ────────────────────────────────────────────────────
@bp.get("/<int:pid>/editar")
@login_required
@role_required("admin", "operador")
def editar_produto(pid: int):
    p = get_produto(pid)
    if not p:
        flash("Produto não encontrado.", "error")
        return redirect(url_for("stock.stock_home"))
    return render_template(
        "stock/form.html",
        produto=p,
        CATEGORIAS=CATEGORIAS,
        CATEGORIAS_LABEL=CATEGORIAS_LABEL,
        UNIDADES=UNIDADES,
    )


@bp.post("/<int:pid>/editar")
@login_required
@role_required("admin", "operador")
def salvar_produto(pid: int):
    try:
        update_produto(pid, dict(request.form))
        flash("Produto atualizado.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("stock.produto_detail", pid=pid))


# ── Movimentação manual (entrada / saída / ajuste) ────────────────────
@bp.post("/<int:pid>/movimentar")
@login_required
@role_required("admin", "operador")
def movimentar(pid: int):
    tipo = request.form.get("tipo", "").upper()
    try:
        registrar_movimentacao(
            produto_id=pid,
            tipo=tipo,
            quantidade=int(request.form.get("quantidade") or 0),
            motivo=request.form.get("motivo", ""),
            usuario=g.user["nome"],
        )
        label = {"ENTRADA": "Entrada", "SAIDA": "Saída", "AJUSTE": "Ajuste"}
        flash(f"{label.get(tipo, tipo)} registrada com sucesso.", "success")
    except (ValueError, TypeError) as e:
        flash(str(e), "error")
    return redirect(url_for("stock.produto_detail", pid=pid))


# ── API: consumo a partir de ticket ──────────────────────────────────
@bp.post("/consumir-ticket")
@login_required
@role_required("admin", "operador")
def consumir_ticket():
    """Registra saída de estoque vinculada a um chamado."""
    try:
        produto_id = int(request.form.get("produto_id") or 0)
        ticket_id  = int(request.form.get("ticket_id") or 0)
        quantidade = int(request.form.get("quantidade") or 0)
        motivo = request.form.get("motivo") or f"Chamado #{ticket_id}"
        registrar_movimentacao(
            produto_id=produto_id,
            tipo=TIPO_SAIDA,
            quantidade=quantidade,
            motivo=motivo,
            ticket_id=ticket_id,
            usuario=g.user["nome"],
        )
        flash("Consumo registrado no estoque.", "success")
    except (ValueError, TypeError) as e:
        flash(str(e), "error")
    # Volta para o ticket de origem
    return redirect(request.referrer or url_for("routes.index"))


# ── API JSON: lista produtos para autocomplete ────────────────────────
@bp.get("/api/produtos")
@login_required
def api_produtos():
    rows = produtos_para_select()
    return jsonify([dict(r) for r in rows])
