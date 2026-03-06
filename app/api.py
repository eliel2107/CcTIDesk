from flask import Blueprint, request, render_template
from app.models import update_status, get_ticket, list_tickets
from app.extensions import limiter, csrf

bp = Blueprint("api", __name__, url_prefix="/api")

# A API usa HMAC/token ou é consumida pelo JS interno — isenta de CSRF de formulário.
# O rate limiting protege contra abuso.

@bp.get("/health")
def health():
    return {"ok": True, "service": "chamados"}

@bp.get("/tickets")
@limiter.limit("200 per hour")
def api_list():
    filters = {k: request.args.get(k, "") for k in ["status","tipo","prioridade","responsavel","q"]}
    rows = list_tickets(filters)
    return {"items": [dict(r) for r in rows], "count": len(rows)}

@bp.get("/tickets/<int:ticket_id>")
def api_get(ticket_id: int):
    row = get_ticket(ticket_id)
    return ({"error":"Chamado não encontrado"},404) if not row else dict(row)

@bp.post("/tickets/<int:ticket_id>/status")
@limiter.limit("120 per hour")
def api_status(ticket_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        update_status(ticket_id, (payload.get("status") or "").strip(), "Atualizado via API/Kanban.")
        return {"ok": True, "id": ticket_id, "status": payload.get("status")}
    except Exception as e:
        return {"error": str(e)}, 400

@bp.get("/assets")
def api_assets():
    from app.services.asset_service import list_assets
    filters = {k: request.args.get(k, "") for k in ["q","status","tipo"]}
    rows = list_assets(filters)
    return {"items": [dict(r) for r in rows], "count": len(rows)}

@bp.get("/assets/<int:asset_id>")
def api_asset_detail(asset_id: int):
    from app.services.asset_service import get_asset
    row = get_asset(asset_id)
    return ({"error":"Ativo não encontrado"},404) if not row else dict(row)

@bp.get("/docs")

def docs():
    routes = [
        {"method":"GET","path":"/api/health","description":"Verifica se a API está ativa"},
        {"method":"GET","path":"/api/tickets","description":"Lista tickets com filtros opcionais"},
        {"method":"GET","path":"/api/tickets/<id>","description":"Retorna um ticket por ID"},
        {"method":"POST","path":"/api/tickets/<id>/status","description":"Atualiza status do ticket"},
        {"method":"GET","path":"/api/assets","description":"Lista ativos com filtros opcionais"},
        {"method":"GET","path":"/api/assets/<id>","description":"Retorna um ativo por ID"},
    ]
    return render_template("api_docs.html", routes=routes)
