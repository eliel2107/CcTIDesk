"""Serviço de Dashboard e Métricas."""

from datetime import datetime, timedelta
from app.db import get_db
from app.helpers import _now, _today_ymd, _parse_dt, _days_between
from app.services.ticket_service import get_overdue_tickets


def dashboard_stats():
    db = get_db()
    rows = db.execute("SELECT status, COUNT(*) as total FROM tickets GROUP BY status").fetchall()
    by_status = {r["status"]: r["total"] for r in rows}
    total = db.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]
    today = _today_ymd()
    overdue_rows = get_overdue_tickets(today)
    overdue = len(overdue_rows)
    upcoming = db.execute("""SELECT id, titulo, status, prioridade, responsavel, data_limite
      FROM tickets WHERE data_limite IS NOT NULL AND data_limite >= ? AND status NOT IN ('CONCLUIDO','CANCELADO')
      ORDER BY data_limite ASC LIMIT 10""", (today,)).fetchall()
    return {"total": total, "by_status": by_status, "overdue": overdue, "overdue_rows": overdue_rows, "upcoming": upcoming, "today": today}


def dashboard_stats_advanced(user_id: int = None, user_role: str = None):
    db = get_db()
    today = _today_ymd()
    scope_sql = ""
    scope_params: list = []
    if user_role == "operador" and user_id:
        scope_sql = " AND assigned_user_id = ?"
        scope_params = [user_id]

    def qone(sql, params=()):
        return db.execute(sql, list(params)).fetchone()
    def qall(sql, params=()):
        return db.execute(sql, list(params)).fetchall()

    total = qone(f"SELECT COUNT(*) as c FROM tickets WHERE 1=1{scope_sql}", scope_params)["c"]
    by_status = {r["status"]: r["total"] for r in qall(f"SELECT status, COUNT(*) as total FROM tickets WHERE 1=1{scope_sql} GROUP BY status", scope_params)}
    by_tipo = {r["tipo"]: r["total"] for r in qall(f"SELECT tipo, COUNT(*) as total FROM tickets WHERE 1=1{scope_sql} GROUP BY tipo", scope_params)}
    by_prioridade = {r["prioridade"]: r["total"] for r in qall(f"SELECT prioridade, COUNT(*) as total FROM tickets WHERE 1=1{scope_sql} GROUP BY prioridade", scope_params)}

    overdue_rows = qall(f"""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite, criado_em
        FROM tickets
        WHERE data_limite IS NOT NULL AND data_limite < ? AND status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
        ORDER BY data_limite ASC""", [today] + scope_params)
    overdue = []
    for r in overdue_rows:
        try:
            days_late = _days_between(r["data_limite"], today)
        except Exception:
            days_late = None
        overdue.append({**dict(r), "days_late": days_late})

    upcoming_rows = qall(f"""SELECT id, tipo, titulo, responsavel, prioridade, status, data_limite
      FROM tickets
      WHERE data_limite IS NOT NULL AND data_limite >= ? AND status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
      ORDER BY data_limite ASC LIMIT 20""", [today] + scope_params)
    upcoming = []
    for r in upcoming_rows:
        try:
            days_to = abs(_days_between(r["data_limite"], today))
        except Exception:
            days_to = None
        upcoming.append({**dict(r), "days_to_due": days_to})

    open_rows = qall(f"""SELECT id, titulo, tipo, status, prioridade, responsavel, criado_em
        FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
        ORDER BY criado_em ASC""", scope_params)
    aging_buckets = {"0-2": 0, "3-7": 0, "8-14": 0, "15-30": 0, "31+": 0}
    oldest = []
    for r in open_rows:
        created = (r["criado_em"] or "")[:10]
        try:
            age = _days_between(created, today)
        except Exception:
            age = None
        bucket = None
        if age is not None:
            if age <= 2: bucket = "0-2"
            elif age <= 7: bucket = "3-7"
            elif age <= 14: bucket = "8-14"
            elif age <= 30: bucket = "15-30"
            else: bucket = "31+"
        if bucket:
            aging_buckets[bucket] += 1
        oldest.append({**dict(r), "age_days": age})
    oldest = sorted([o for o in oldest if o["age_days"] is not None], key=lambda x: x["age_days"], reverse=True)[:15]

    top_resp_rows = qall(f"""SELECT COALESCE(NULLIF(responsavel,''), '(sem responsável)') as resp, COUNT(*) as total
        FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}
        GROUP BY resp ORDER BY total DESC, resp ASC LIMIT 10""", scope_params)
    top_responsaveis = [dict(r) for r in top_resp_rows]

    since = (datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=30)).strftime("%Y-%m-%d")
    done_rows = qall(f"""SELECT tl.criado_em FROM ticket_log tl
        JOIN tickets t ON t.id = tl.ticket_id
        WHERE tl.evento='CONCLUIDO_SOLICITANTE' AND substr(tl.criado_em,1,10) >= ?{scope_sql.replace('assigned_user_id','t.assigned_user_id')}""",
        [since] + scope_params)
    concluded_30d = len(done_rows)

    open_count = qone(f"SELECT COUNT(*) as c FROM tickets WHERE status NOT IN ('CONCLUIDO','CANCELADO'){scope_sql}", scope_params)["c"]
    closed_count = qone(f"SELECT COUNT(*) as c FROM tickets WHERE status IN ('CONCLUIDO','CANCELADO'){scope_sql}", scope_params)["c"]

    return {
        "today": today, "total": total, "by_status": by_status, "by_tipo": by_tipo,
        "by_prioridade": by_prioridade, "open_count": open_count, "closed_count": closed_count,
        "overdue": overdue, "upcoming": upcoming, "aging_buckets": aging_buckets,
        "oldest": oldest, "top_responsaveis": top_responsaveis, "concluded_30d": concluded_30d,
    }


def ticket_report_metrics(start_date=None, end_date=None, sla_days=3):
    db = get_db()
    q = """SELECT id, tipo, titulo, solicitante, responsavel, prioridade, status, data_limite,
                  asset_id, criado_em, atualizado_em, closed_em
           FROM tickets WHERE 1=1"""
    params = []
    if start_date:
        q += " AND substr(criado_em,1,10) >= ?"; params.append(start_date)
    if end_date:
        q += " AND substr(criado_em,1,10) <= ?"; params.append(end_date)
    q += " ORDER BY criado_em DESC"
    rows = db.execute(q, params).fetchall()
    items = [dict(r) for r in rows]
    resolved = []
    for item in items:
        c = _parse_dt(item.get("criado_em"))
        f = _parse_dt(item.get("closed_em"))
        if c and f:
            hours = round((f - c).total_seconds() / 3600.0, 2)
            days = round(hours / 24.0, 2)
            item["resolution_hours"] = hours
            item["resolution_days"] = days
            item["within_sla"] = days <= sla_days
            resolved.append(item)
        else:
            item["resolution_hours"] = None
            item["resolution_days"] = None
            item["within_sla"] = None
    avg_days = round(sum(i["resolution_days"] for i in resolved) / len(resolved), 2) if resolved else 0
    within_sla_count = sum(1 for i in resolved if i["within_sla"])
    outside_sla_count = sum(1 for i in resolved if i["within_sla"] is False)
    within_sla_pct = round((within_sla_count / len(resolved)) * 100, 1) if resolved else 0
    by_status, by_tipo, by_responsavel = {}, {}, {}
    for item in items:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        by_tipo[item["tipo"]] = by_tipo.get(item["tipo"], 0) + 1
        resp = item["responsavel"] or "(sem responsável)"
        by_responsavel[resp] = by_responsavel.get(resp, 0) + 1
    top_responsaveis = sorted(by_responsavel.items(), key=lambda x: (-x[1], x[0]))[:10]
    return {
        "items": items, "resolved_items": resolved, "total": len(items),
        "resolved_total": len(resolved), "avg_resolution_days": avg_days,
        "within_sla_count": within_sla_count, "outside_sla_count": outside_sla_count,
        "within_sla_pct": within_sla_pct, "by_status": by_status, "by_tipo": by_tipo,
        "top_responsaveis": top_responsaveis, "start_date": start_date,
        "end_date": end_date, "sla_days": sla_days,
    }
