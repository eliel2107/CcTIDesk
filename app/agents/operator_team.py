"""
Time de Suporte ao Operador — 3 agentes em sequência.

Funciona com Gemini (AI_API_KEY) ou Claude (ANTHROPIC_API_KEY).
O contexto do banco é pré-buscado e incluído nos prompts — não requer tool use.

Fluxo:
  1. Agente Diagnóstico  → analisa o problema com KB + tickets similares como contexto
  2. Agente Checklist    → sugere etapas usando o checklist padrão da categoria
  3. Agente Rascunho     → redige resposta para o solicitante
"""

import json
import re

from flask import current_app

from .tools import buscar_checklist_categoria, buscar_kb, buscar_tickets_similares


# ── Extração de JSON ──────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


# ── Seleção de provider ───────────────────────────────────────────────────────


def _make_generate(app_config: dict):
    """
    Retorna uma função generate(system, prompt) -> str
    usando Gemini ou Claude conforme configuração.
    Prioridade: ANTHROPIC_API_KEY > AI_API_KEY (Gemini).
    """
    anthropic_key = (app_config.get("ANTHROPIC_API_KEY") or "").strip()
    gemini_key    = (app_config.get("AI_API_KEY") or "").strip()

    if anthropic_key:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=anthropic_key)
        model  = app_config.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

        def _generate_claude(system: str, prompt: str) -> str:
            resp = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            for block in resp.content:
                if block.type == "text":
                    return block.text
            return ""

        return _generate_claude

    if gemini_key:
        from app.services.ai.gemini_client import GeminiClient
        client = GeminiClient(
            api_key=gemini_key,
            model=app_config.get("AI_MODEL", "gemini-1.5-flash"),
            base_url=app_config.get(
                "AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
            ),
            timeout_seconds=int(app_config.get("AI_TIMEOUT_SECONDS", 45) or 45),
        )

        def _generate_gemini(system: str, prompt: str) -> str:
            return client.generate_text(f"{system}\n\n{prompt}")

        return _generate_gemini

    raise ValueError(
        "Nenhuma chave de IA configurada. "
        "Defina AI_API_KEY (Gemini) ou ANTHROPIC_API_KEY (Claude) no .env."
    )


# ── Pré-busca de contexto ─────────────────────────────────────────────────────


def _fetch_context(ticket: dict) -> dict:
    """Busca KB, tickets similares e checklist da categoria antes de chamar a IA."""
    titulo = ticket.get("titulo") or ""
    categoria_id = ticket.get("categoria_id")
    query = titulo[:120]

    kb      = buscar_kb(query, categoria_id) if query else "Sem dados."
    similar = buscar_tickets_similares(query, categoria_id) if query else "Sem dados."
    steps   = buscar_checklist_categoria(categoria_id) if categoria_id else "Categoria não informada."

    return {"kb": kb, "similar": similar, "steps": steps}


# ── Agente 1: Diagnóstico ─────────────────────────────────────────────────────


def _run_diagnostic(generate, ticket_summary: str, ctx: dict) -> dict:
    system = (
        "Você é um especialista em suporte de TI analisando chamados de service desk. "
        "Baseie suas conclusões APENAS nos dados de contexto fornecidos. Seja objetivo e técnico."
    )
    prompt = (
        "Analise o chamado abaixo usando o contexto fornecido.\n\n"
        "Responda APENAS com JSON no formato exato:\n"
        '{"diagnostico":"...","causa_provavel":"...","solucao_sugerida":"...","referencias":["..."]}\n\n'
        f"CHAMADO:\n{ticket_summary}\n\n"
        f"BASE DE CONHECIMENTO RELACIONADA:\n{ctx['kb']}\n\n"
        f"CHAMADOS SIMILARES RESOLVIDOS:\n{ctx['similar']}"
    )
    text   = generate(system, prompt)
    result = _extract_json(text)
    if not result:
        result = {
            "diagnostico": text,
            "causa_provavel": "",
            "solucao_sugerida": "",
            "referencias": [],
        }
    return result


# ── Agente 2: Checklist ───────────────────────────────────────────────────────


def _run_checklist(generate, ticket_summary: str, diagnostic: dict, ctx: dict) -> list:
    system = (
        "Você é um especialista em ITSM criando checklists de atendimento. "
        "As etapas devem ser claras, acionáveis e ordenadas logicamente."
    )
    prompt = (
        "Com base no chamado, diagnóstico e etapas padrão abaixo, crie um checklist "
        "de até 7 etapas concretas para o operador seguir.\n\n"
        'Responda APENAS com JSON: {"checklist":["etapa 1","etapa 2",...]}\n\n'
        f"CHAMADO:\n{ticket_summary}\n\n"
        f"DIAGNÓSTICO: {diagnostic.get('diagnostico','')}\n"
        f"SOLUÇÃO SUGERIDA: {diagnostic.get('solucao_sugerida','')}\n\n"
        f"ETAPAS PADRÃO DA CATEGORIA:\n{ctx['steps']}"
    )
    text = generate(system, prompt)
    data = _extract_json(text)
    return data.get("checklist", [])


# ── Agente 3: Rascunho de Resposta ───────────────────────────────────────────


def _run_draft(generate, ticket_summary: str, diagnostic: dict) -> str:
    system = (
        "Você é um operador de service desk experiente escrevendo respostas "
        "profissionais e empáticas para usuários."
    )
    prompt = (
        "Escreva um rascunho de resposta para o solicitante deste chamado.\n"
        "A resposta deve:\n"
        "- Confirmar que o chamado foi recebido e entendido\n"
        "- Informar brevemente o que será investigado ou feito\n"
        "- Ser cordial, profissional e ter no máximo 120 palavras\n\n"
        "Escreva APENAS o texto da resposta, sem explicações adicionais.\n\n"
        f"CHAMADO:\n{ticket_summary}\n\n"
        f"DIAGNÓSTICO: {diagnostic.get('diagnostico','')}\n"
        f"SOLUÇÃO SUGERIDA: {diagnostic.get('solucao_sugerida','')}"
    )
    return generate(system, prompt)


# ── Orquestrador principal ────────────────────────────────────────────────────


def run_operator_assist(ticket: dict) -> dict:
    """
    Executa o time de suporte ao operador e retorna o resultado combinado.

    Retorna:
        {
            "enabled": True,
            "provider": "gemini" | "claude",
            "diagnostico": {"diagnostico":..., "causa_provavel":...,
                            "solucao_sugerida":..., "referencias":[...]},
            "checklist": ["etapa 1", ...],
            "rascunho_resposta": "..."
        }
        ou {"enabled": False, "error": "..."}
    """
    cfg = current_app.config

    try:
        generate = _make_generate(cfg)
    except ValueError as e:
        return {"enabled": False, "error": str(e)}

    provider = "claude" if (cfg.get("ANTHROPIC_API_KEY") or "").strip() else "gemini"

    categoria_id = ticket.get("categoria_id")
    ticket_summary = (
        f"Número: {ticket.get('numero_chamado', '-')}\n"
        f"Título: {ticket.get('titulo', '-')}\n"
        f"Descrição: {(ticket.get('descricao') or '')[:800]}\n"
        f"Prioridade: {ticket.get('prioridade', '-')}\n"
        f"Status: {ticket.get('status', '-')}"
    )

    try:
        ctx = _fetch_context(ticket)
    except Exception as e:
        current_app.logger.exception("Falha ao buscar contexto do banco")
        ctx = {"kb": "Erro ao buscar KB.", "similar": "Erro ao buscar tickets.", "steps": ""}

    try:
        diagnostic = _run_diagnostic(generate, ticket_summary, ctx)
    except Exception as e:
        current_app.logger.exception("Agente Diagnóstico falhou")
        diagnostic = {"diagnostico": f"Erro: {e}", "causa_provavel": "", "solucao_sugerida": "", "referencias": []}

    try:
        checklist = _run_checklist(generate, ticket_summary, diagnostic, ctx)
    except Exception as e:
        current_app.logger.exception("Agente Checklist falhou")
        checklist = []

    try:
        draft = _run_draft(generate, ticket_summary, diagnostic)
    except Exception as e:
        current_app.logger.exception("Agente Rascunho falhou")
        draft = f"Erro ao gerar rascunho: {e}"

    return {
        "enabled": True,
        "provider": provider,
        "diagnostico": diagnostic,
        "checklist": checklist,
        "rascunho_resposta": draft,
    }
