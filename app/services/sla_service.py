"""Serviço de SLA e TMA (Tempo Médio de Atendimento)."""

from datetime import datetime, timedelta
from typing import Optional

from app.db import get_db
from app.helpers import _now


def calc_sla_deadline(categoria_id: int, criado_em: str = None) -> Optional[str]:
    if not categoria_id:
        return None
    db = get_db()
    row = db.execute("SELECT sla_horas FROM categories WHERE id=?", (categoria_id,)).fetchone()
    if not row or not row["sla_horas"]:
        return None
    base = datetime.strptime((criado_em or _now())[:19], "%Y-%m-%d %H:%M:%S")
    deadline = base + timedelta(hours=row["sla_horas"])
    return deadline.strftime("%Y-%m-%d %H:%M:%S")


def get_sla_status(ticket) -> str:
    if not ticket["sla_deadline"] or ticket["status"] in ("CONCLUIDO", "CANCELADO"):
        return "none"
    now = datetime.now()
    try:
        criado = datetime.strptime(str(ticket["criado_em"])[:19], "%Y-%m-%d %H:%M:%S")
        deadline = datetime.strptime(str(ticket["sla_deadline"])[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "none"
    total = (deadline - criado).total_seconds()
    remaining = (deadline - now).total_seconds()
    if remaining < 0:
        return "breach"
    if total > 0 and (remaining / total) <= 0.20:
        return "warning"
    return "ok"


def calcular_tma_minutos(ticket_id: int) -> Optional[int]:
    db = get_db()
    t = db.execute("SELECT criado_em, closed_em FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t or not t["closed_em"]:
        return None
    try:
        inicio = datetime.strptime(str(t["criado_em"])[:19], "%Y-%m-%d %H:%M:%S")
        fim = datetime.strptime(str(t["closed_em"])[:19], "%Y-%m-%d %H:%M:%S")
        return max(0, int((fim - inicio).total_seconds() / 60))
    except Exception:
        return None


def gravar_tma(ticket_id: int):
    mins = calcular_tma_minutos(ticket_id)
    if mins is not None:
        db = get_db()
        db.execute("UPDATE tickets SET tma_minutos=? WHERE id=?", (mins, ticket_id))
        db.commit()


def tma_stats(user_id: int = None, categoria_id: int = None) -> dict:
    db = get_db()
    q = "SELECT tma_minutos FROM tickets WHERE status='CONCLUIDO' AND tma_minutos IS NOT NULL"
    params = []
    if user_id:
        q += " AND assigned_user_id=?"; params.append(user_id)
    if categoria_id:
        q += " AND categoria_id=?"; params.append(categoria_id)
    rows = db.execute(q, params).fetchall()
    if not rows:
        return {"media": None, "minimo": None, "maximo": None, "total": 0}
    vals = [r["tma_minutos"] for r in rows]
    return {"media": round(sum(vals) / len(vals)), "minimo": min(vals), "maximo": max(vals), "total": len(vals)}
