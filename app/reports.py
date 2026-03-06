from flask import Blueprint, render_template, request, Response
from app.auth import login_required
from app.models import ticket_report_metrics
from app.services.asset_service import asset_dashboard
from app.services.report_service import build_tickets_xlsx, build_assets_xlsx, build_tickets_pdf, build_assets_pdf

bp = Blueprint("reports", __name__, url_prefix="/reports")

@bp.get("/")
@login_required
def reports_home():
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    sla_days = int((request.args.get("sla_days") or "3").strip() or "3")
    ticket_stats = ticket_report_metrics(start_date, end_date, sla_days)
    asset_stats = asset_dashboard()
    return render_template("reports.html", ticket_stats=ticket_stats, asset_stats=asset_stats, start_date=start_date or "", end_date=end_date or "", sla_days=sla_days)

@bp.get("/tickets.xlsx")
@login_required
def tickets_xlsx():
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    sla_days = int((request.args.get("sla_days") or "3").strip() or "3")
    content = build_tickets_xlsx(start_date, end_date, sla_days)
    return Response(content, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":"attachment; filename=relatorio_chamados_sla.xlsx"})

@bp.get("/tickets.pdf")
@login_required
def tickets_pdf():
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    sla_days = int((request.args.get("sla_days") or "3").strip() or "3")
    content = build_tickets_pdf(start_date, end_date, sla_days)
    return Response(content, mimetype="application/pdf", headers={"Content-Disposition":"attachment; filename=relatorio_chamados_sla.pdf"})

@bp.get("/assets.xlsx")
@login_required
def assets_xlsx():
    content = build_assets_xlsx()
    return Response(content, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":"attachment; filename=relatorio_ativos.xlsx"})

@bp.get("/assets.pdf")
@login_required
def assets_pdf():
    content = build_assets_pdf()
    return Response(content, mimetype="application/pdf", headers={"Content-Disposition":"attachment; filename=relatorio_ativos.pdf"})
