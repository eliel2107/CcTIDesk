"""
Camada de compatibilidade — re-exporta de services/ para que imports antigos continuem funcionando.

USO NOVO (preferido):
    from app.services.ticket_service import create_ticket, get_ticket
    from app.services.sla_service import get_sla_status

USO ANTIGO (funciona via este módulo):
    from app.models import create_ticket, get_ticket, get_sla_status
"""

# ── Constantes ──────────────────────────────────────────────────────────
from app.constants import (  # noqa: F401
    STATUSES, CLASSIFICATIONS, TYPES, PRIORITIES,
    QUEUE_VISIBLE_STATUSES, FINAL_STATUSES, LOCKED_STATUSES,
    SUGGESTED_STEPS, TRANSICOES_VALIDAS,
)

# ── Helpers ─────────────────────────────────────────────────────────────
from app.helpers import (  # noqa: F401
    _now, _today_ymd, _parse_dt, _clean, _parse_float,
    _validate_date_ymd, validate_choice, _escape_like, _like_param,
    _days_between,
)

# ── Ticket Service ──────────────────────────────────────────────────────
from app.services.ticket_service import (  # noqa: F401
    log_event, _log_asset_history,
    create_ticket, get_ticket, get_logs, list_tickets,
    list_tickets_paginated, list_tickets_by_requester, list_queue_tickets,
    update_status, update_fields,
    finalizar_ticket, confirmar_conclusao, rejeitar_conclusao,
    assign_ticket, auto_assign_overdue_tickets, get_overdue_tickets,
    _auto_assign, _fallback_assign, _next_numero, _category_default_priority,
    list_steps, toggle_step, add_step, delete_step, move_step,
    normalize_steps, _insert_steps,
    list_attachments, get_attachment, count_attachments, add_attachment, delete_attachment,
    seed_example,
)

# ── SLA Service ─────────────────────────────────────────────────────────
from app.services.sla_service import (  # noqa: F401
    calc_sla_deadline, get_sla_status,
    calcular_tma_minutos, gravar_tma, tma_stats,
)

# ── Approval Service ───────────────────────────────────────────────────
from app.services.approval_service import (  # noqa: F401
    solicitar_aprovacao, aprovar_ticket, reprovar_ticket, precisa_aprovacao,
)

# ── Workflow Service ───────────────────────────────────────────────────
from app.services.workflow_service import (  # noqa: F401
    transfer_ticket, get_transfers,
    reabrir_ticket, devolver_ao_solicitante, reenviar_pelo_solicitante,
)

# ── Comment Service ────────────────────────────────────────────────────
from app.services.comment_service import (  # noqa: F401
    add_comment, get_comments, delete_comment,
)

# ── Webhook Service ────────────────────────────────────────────────────
from app.services.webhook_service import (  # noqa: F401
    list_webhooks, create_webhook, update_webhook, delete_webhook,
    fire_webhooks,
)

# ── Group Service ──────────────────────────────────────────────────────
from app.services.group_service import (  # noqa: F401
    list_groups, get_group, create_group, update_group,
    set_group_members, set_group_categories,
    get_group_members, get_group_categories,
    assign_ticket_to_group,
)

# ── Category Service ───────────────────────────────────────────────────
from app.services.category_service import (  # noqa: F401
    list_categories, get_category, create_category, update_category,
    delete_category, get_user_categories, set_user_categories,
    create_category_full, update_category_full,
)

# ── Search Service ─────────────────────────────────────────────────────
from app.services.search_service import (  # noqa: F401
    search_tickets_advanced,
)

# ── Dashboard Service ──────────────────────────────────────────────────
from app.services.dashboard_service import (  # noqa: F401
    dashboard_stats, dashboard_stats_advanced,
    ticket_report_metrics,
)
