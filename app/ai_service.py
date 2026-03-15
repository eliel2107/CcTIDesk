
import json
import re
from datetime import datetime

from flask import current_app

from .db import get_db
from .services.ai.gemini_client import GeminiClient, GeminiClientError


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _enabled() -> bool:
    return bool(current_app.config.get('AI_ASSIST_ENABLED'))


def _mask_sensitive(text: str) -> str:
    if not text:
        return ''
    text = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email]', text)
    text = re.sub(r'(?:\d[ -]*?){8,}', '[numero]', text)
    return text


def _truncate(text: str) -> str:
    limit = int(current_app.config.get('AI_MAX_CONTEXT_CHARS', 6000) or 6000)
    return (text or '')[:limit]


def _client() -> GeminiClient:
    return GeminiClient(
        api_key=current_app.config.get('AI_API_KEY', ''),
        model=current_app.config.get('AI_MODEL', 'gemini-1.5-flash'),
        base_url=current_app.config.get('AI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta'),
        timeout_seconds=int(current_app.config.get('AI_TIMEOUT_SECONDS', 30) or 30),
    )


def opening_assistant(description: str, title: str = '', category: str = '') -> dict:
    if not _enabled():
        return {'enabled': False, 'message': 'IA assistida desativada no ambiente.'}
    safe_title = _mask_sensitive(_truncate(title))
    safe_desc = _mask_sensitive(_truncate(description))
    safe_cat = _mask_sensitive(_truncate(category))
    prompt = f"""Você é um assistente de service desk.
Analise o chamado abaixo e responda em português simples com EXACTAMENTE estas seções:
MELHORIA_DA_DESCRICAO:
PASSOS_INICIAIS_SUGERIDOS:
ARTIGOS_OU_PALAVRAS_CHAVE:

Categoria: {safe_cat or '-'}
Título: {safe_title or '-'}
Descrição: {safe_desc or '-'}

Regras:
- Seja objetivo.
- Não invente acesso ou ações que o usuário não possa executar.
- Sugira no máximo 5 passos.
- Se faltar contexto, diga o que pedir.
"""
    text = _client().generate_text(prompt)
    return {'enabled': True, 'text': text}


def resolution_assistant(ticket_id: int, resolution_text: str, title: str = '', description: str = '') -> dict:
    if not _enabled():
        return {'enabled': False, 'message': 'IA assistida desativada no ambiente.'}
    safe_resolution = _mask_sensitive(_truncate(resolution_text))
    safe_title = _mask_sensitive(_truncate(title))
    safe_desc = _mask_sensitive(_truncate(description))
    prompt = f"""Você é um assistente de documentação técnica.
Com base no chamado resolvido abaixo, gere um rascunho de artigo em português com EXACTAMENTE estas seções:
TITULO:
RESUMO:
CAUSA_PROVAVEL:
PASSOS_DE_RESOLUCAO:
VALIDACAO_FINAL:

Título do chamado: {safe_title or '-'}
Descrição inicial: {safe_desc or '-'}
Solução aplicada: {safe_resolution or '-'}

Regras:
- Seja técnico, claro e curto.
- Use passos numerados na seção PASSOS_DE_RESOLUCAO.
- Não inclua dados sensíveis.
"""
    text = _client().generate_text(prompt)
    db = get_db()
    now = _now()
    db.execute(
        'INSERT INTO ticket_ai_insights(ticket_id, insight_type, title, content, created_em) VALUES(?,?,?,?,?)',
        (ticket_id, 'resolution_draft', 'Rascunho de documentação gerado por IA', text, now),
    )
    db.execute(
        'INSERT INTO ai_jobs(ticket_id, job_type, status, payload, result_text, created_em, updated_em) VALUES(?,?,?,?,?,?,?)',
        (ticket_id, 'generate_resolution_draft', 'completed', json.dumps({'resolution_length': len(resolution_text or '')}), text, now, now),
    )
    db.commit()
    return {'enabled': True, 'text': text}


def last_ticket_insight(ticket_id: int):
    db = get_db()
    return db.execute(
        'SELECT * FROM ticket_ai_insights WHERE ticket_id=? ORDER BY id DESC LIMIT 1',
        (ticket_id,),
    ).fetchone()
