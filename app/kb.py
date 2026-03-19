"""
Base de Conhecimento (KB) — artigos de solução que operadores criam ao fechar chamados.
"""
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from .auth import login_required, role_required
from .db import get_db
from .models import _now, list_categories

bp = Blueprint("kb", __name__, url_prefix="/kb")


def _get_article(article_id: int):
    return get_db().execute("SELECT * FROM kb_articles WHERE id=?", (article_id,)).fetchone()


def list_articles(q: str = "", categoria_id: str = "", publico_only: bool = False, limit: int = 50):
    db = get_db()
    sql = "SELECT k.*, c.nome as categoria_nome, c.cor as categoria_cor FROM kb_articles k LEFT JOIN categories c ON c.id=k.categoria_id WHERE 1=1"
    params = []
    if publico_only:
        sql += " AND k.publico=1"
    if q:
        like = f"%{q}%"
        sql += " AND (k.titulo LIKE ? OR k.conteudo LIKE ? OR k.tags LIKE ?)"
        params.extend([like, like, like])
    if categoria_id and str(categoria_id).isdigit():
        sql += " AND k.categoria_id=?"; params.append(int(categoria_id))
    sql += " ORDER BY k.visualizacoes DESC, k.atualizado_em DESC LIMIT ?"
    params.append(limit)
    return db.execute(sql, params).fetchall()


def suggest_articles(titulo: str, categoria_id: int = None, limit: int = 3):
    """Sugere artigos relacionados baseado no título do chamado."""
    db = get_db()
    words = [w for w in titulo.lower().split() if len(w) > 3][:5]
    if not words:
        return []
    conditions = " OR ".join(["(k.titulo LIKE ? OR k.tags LIKE ?)" for _ in words])
    params = []
    for w in words:
        params.extend([f"%{w}%", f"%{w}%"])
    sql = f"SELECT k.id, k.titulo, k.visualizacoes FROM kb_articles k WHERE k.publico=1 AND ({conditions})"
    if categoria_id:
        sql += " AND k.categoria_id=?"; params.append(categoria_id)
    sql += " ORDER BY k.visualizacoes DESC LIMIT ?"
    params.append(limit)
    return db.execute(sql, params).fetchall()


# ── Rotas ─────────────────────────────────────────────────────────────────────

@bp.get("/")
@login_required
def kb_index():
    q = request.args.get("q", "")
    cat_id = request.args.get("categoria_id", "")
    articles = list_articles(q=q, categoria_id=cat_id,
                              publico_only=(g.user["role"] == "solicitante"))
    categories = list_categories(only_active=True)
    return render_template("kb_index.html", articles=articles, categories=categories,
                            q=q, cat_id=cat_id)


@bp.get("/<int:article_id>")
@login_required
def kb_article(article_id: int):
    art = _get_article(article_id)
    if not art:
        flash("Artigo não encontrado.", "error")
        return redirect(url_for("kb.kb_index"))
    if not art["publico"] and g.user["role"] == "solicitante":
        flash("Artigo não disponível.", "error")
        return redirect(url_for("kb.kb_index"))
    db = get_db()
    db.execute("UPDATE kb_articles SET visualizacoes=visualizacoes+1 WHERE id=?", (article_id,))
    db.commit()
    related = list_articles(q=art["titulo"][:30], limit=4)
    related = [r for r in related if r["id"] != article_id][:3]
    return render_template("kb_article.html", art=art, related=related)


@bp.get("/novo")
@login_required
@role_required("admin", "operador")
def kb_new():
    ticket_id = request.args.get("ticket_id")
    ticket = None
    if ticket_id:
        from .models import get_ticket
        ticket = get_ticket(int(ticket_id))
    categories = list_categories(only_active=True)
    return render_template("kb_form.html", art=None, ticket=ticket, categories=categories)


@bp.post("/novo")
@login_required
@role_required("admin", "operador")
def kb_create():
    titulo = request.form.get("titulo", "").strip()
    conteudo = request.form.get("conteudo", "").strip()
    if not titulo or not conteudo:
        flash("Título e conteúdo são obrigatórios.", "error")
        return redirect(url_for("kb.kb_new"))
    cat_id = request.form.get("categoria_id", "")
    tags = request.form.get("tags", "").strip()
    publico = request.form.get("publico") == "1"
    ticket_id_raw = request.form.get("ticket_id", "")
    ticket_id = int(ticket_id_raw) if ticket_id_raw.isdigit() else None
    db = get_db()
    t = _now()
    db.execute(
        """INSERT INTO kb_articles (titulo, conteudo, categoria_id, tags, autor_id, autor_nome,
           publico, visualizacoes, ticket_id, criado_em, atualizado_em)
           VALUES (?,?,?,?,?,?,?,0,?,?,?)""",
        (titulo, conteudo,
         int(cat_id) if cat_id.isdigit() else None,
         tags, g.user["id"], g.user["nome"],
         1 if publico else 0, ticket_id, t, t)
    )
    db.commit()
    flash("Artigo criado com sucesso.", "success")
    return redirect(url_for("kb.kb_index"))


@bp.get("/<int:article_id>/editar")
@login_required
@role_required("admin", "operador")
def kb_edit(article_id: int):
    art = _get_article(article_id)
    if not art:
        flash("Artigo não encontrado.", "error")
        return redirect(url_for("kb.kb_index"))
    categories = list_categories(only_active=True)
    return render_template("kb_form.html", art=art, ticket=None, categories=categories)


@bp.post("/<int:article_id>/editar")
@login_required
@role_required("admin", "operador")
def kb_update(article_id: int):
    titulo = request.form.get("titulo", "").strip()
    conteudo = request.form.get("conteudo", "").strip()
    if not titulo or not conteudo:
        flash("Título e conteúdo são obrigatórios.", "error")
        return redirect(url_for("kb.kb_edit", article_id=article_id))
    cat_id = request.form.get("categoria_id", "")
    tags = request.form.get("tags", "").strip()
    publico = request.form.get("publico") == "1"
    db = get_db()
    db.execute(
        "UPDATE kb_articles SET titulo=?, conteudo=?, categoria_id=?, tags=?, publico=?, atualizado_em=? WHERE id=?",
        (titulo, conteudo, int(cat_id) if cat_id.isdigit() else None,
         tags, 1 if publico else 0, _now(), article_id)
    )
    db.commit()
    flash("Artigo atualizado.", "success")
    return redirect(url_for("kb.kb_article", article_id=article_id))


@bp.post("/<int:article_id>/excluir")
@login_required
@role_required("admin")
def kb_delete(article_id: int):
    db = get_db()
    db.execute("DELETE FROM kb_articles WHERE id=?", (article_id,))
    db.commit()
    flash("Artigo removido.", "success")
    return redirect(url_for("kb.kb_index"))


@bp.get("/api/sugestoes")
@login_required
def kb_suggest_api():
    """API usada pelo formulário de novo chamado para sugerir artigos."""
    titulo = request.args.get("q", "")
    cat_id = request.args.get("categoria_id", "")
    arts = suggest_articles(titulo, int(cat_id) if cat_id.isdigit() else None)
    return jsonify([{"id": a["id"], "titulo": a["titulo"]} for a in arts])
