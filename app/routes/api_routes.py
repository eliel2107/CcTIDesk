"""Endpoints de API internos (notificações, IA, TMA, busca global)."""

from flask import request, jsonify, url_for, g, current_app

from app.routes import bp
from app.auth.decorators import login_required, role_required
from app.db import get_db
from app import ai_service
from app.services.ai.gemini_client import GeminiClientError
from app.services.ticket_service import get_ticket
from app.services.sla_service import tma_stats
from app.address_book import DELIVERY_PRESETS, SENDER_PRESETS
from app.notifications import get_notificacoes, contar_nao_lidas, marcar_lida, marcar_todas_lidas


# ── Address Book ─────────────────────────────────────────────────────────

@bp.get("/api/address-book")
@login_required
def api_address_book():
    return {"delivery": DELIVERY_PRESETS, "sender": SENDER_PRESETS}


# ── Notificações ─────────────────────────────────────────────────────────

@bp.get("/api/notificacoes")
@login_required
def api_notificacoes():
    notifs = get_notificacoes(g.user["id"], limite=20)
    nao_lidas = contar_nao_lidas(g.user["id"])
    return jsonify({
        "nao_lidas": nao_lidas,
        "notificacoes": [
            {"id": n["id"], "tipo": n["tipo"], "titulo": n["titulo"], "mensagem": n["mensagem"],
             "ticket_id": n["ticket_id"], "lida": bool(n["lida"]), "criado_em": n["criado_em"]}
            for n in notifs
        ]
    })


@bp.post("/api/notificacoes/<int:notif_id>/ler")
@login_required
def api_marcar_lida(notif_id: int):
    marcar_lida(notif_id, g.user["id"])
    return jsonify({"ok": True})


@bp.post("/api/notificacoes/ler-todas")
@login_required
def api_marcar_todas_lidas():
    marcar_todas_lidas(g.user["id"])
    return jsonify({"ok": True})


# ── IA ───────────────────────────────────────────────────────────────────

@bp.post("/api/ai/opening-assistant")
@login_required
def api_ai_opening_assistant():
    data = request.get_json(silent=True) or {}
    try:
        result = ai_service.opening_assistant(
            description=(data.get('descricao') or '').strip(),
            title=(data.get('titulo') or '').strip(),
            category=(data.get('categoria') or '').strip(),
        )
        return jsonify(result)
    except GeminiClientError as e:
        return jsonify({'enabled': True, 'error': str(e)}), 502
    except Exception as e:
        current_app.logger.exception('Falha no assistente de abertura')
        return jsonify({'enabled': True, 'error': f'Falha ao consultar IA: {e}'}), 500


@bp.post("/api/ai/tickets/<int:ticket_id>/resolution-draft")
@login_required
@role_required('admin', 'operador')
def api_ai_resolution_draft(ticket_id: int):
    t = get_ticket(ticket_id)
    if not t:
        return jsonify({'error': 'Chamado não encontrado.'}), 404
    data = request.get_json(silent=True) or {}
    resolution = (data.get('resolution') or '').strip()
    if not resolution:
        return jsonify({'error': 'Informe a resolução aplicada.'}), 400
    try:
        result = ai_service.resolution_assistant(
            ticket_id=ticket_id, resolution_text=resolution,
            title=t['titulo'] or '', description=t['descricao'] or '',
        )
        return jsonify(result)
    except GeminiClientError as e:
        return jsonify({'enabled': True, 'error': str(e)}), 502
    except Exception as e:
        current_app.logger.exception('Falha ao gerar rascunho de resolução')
        return jsonify({'enabled': True, 'error': f'Falha ao consultar IA: {e}'}), 500


# ── TMA ──────────────────────────────────────────────────────────────────

@bp.get("/api/tma")
@login_required
def api_tma():
    uid = request.args.get("user_id")
    cid = request.args.get("categoria_id")
    stats = tma_stats(
        user_id=int(uid) if uid and uid.isdigit() else None,
        categoria_id=int(cid) if cid and cid.isdigit() else None,
    )
    return jsonify(stats)


# ── Busca Global (⌘K) ───────────────────────────────────────────────────

@bp.get("/api/search")
@login_required
def global_search_api():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify(results=[])

    db = get_db()
    like = f"%{q}%"
    results = []
    uid = g.user["id"]
    role = g.user["role"]

    # Chamados — com filtro de escopo
    scope = ""
    scope_params = []
    if role == "solicitante":
        scope = " AND t.requester_user_id = ?"
        scope_params = [uid]
    elif role == "operador":
        allowed = db.execute("SELECT category_id FROM user_categories WHERE user_id=?", (uid,)).fetchall()
        ids = [r["category_id"] for r in allowed]
        if ids:
            scope = f" AND t.categoria_id IN ({','.join('?' * len(ids))})"
            scope_params = ids

    ticket_rows = db.execute(
        f"""SELECT t.id, t.numero_chamado, t.titulo, t.status, t.prioridade
            FROM tickets t WHERE (t.titulo LIKE ? OR t.numero_chamado LIKE ? OR t.solicitante LIKE ?){scope}
            ORDER BY t.atualizado_em DESC LIMIT 8""",
        [like, like, like] + scope_params
    ).fetchall()
    for r in ticket_rows:
        results.append({
            "type": "ticket", "id": r["id"],
            "label": f"{r['numero_chamado'] or '#' + str(r['id'])} — {r['titulo']}",
            "sub": f"{r['status'].replace('_', ' ')} · {r['prioridade']}",
            "url": url_for("routes.ticket_detail", ticket_id=r["id"]),
        })

    # KB
    kb_rows = db.execute(
        "SELECT id, titulo FROM kb_articles WHERE (titulo LIKE ? OR tags LIKE ? OR conteudo LIKE ?) AND publico=1 LIMIT 4",
        [like, like, like]
    ).fetchall()
    for r in kb_rows:
        results.append({
            "type": "kb", "id": r["id"], "label": r["titulo"],
            "sub": "Base de conhecimento", "url": url_for("kb.kb_article", article_id=r["id"]),
        })

    # Usuários (só admin)
    if role == "admin":
        user_rows = db.execute(
            "SELECT id, nome, email, role FROM users WHERE nome LIKE ? OR email LIKE ? LIMIT 4",
            [like, like]
        ).fetchall()
        for r in user_rows:
            results.append({
                "type": "user", "id": r["id"], "label": r["nome"],
                "sub": f"{r['email']} · {r['role']}", "url": url_for("admin.users"),
            })

    return jsonify(results=results)
