"""
Ferramentas de banco de dados para os agentes do time de suporte ao operador.
"""

from app.db import get_db


def buscar_kb(query: str, categoria_id: int = None) -> str:
    """Busca artigos relevantes na base de conhecimento."""
    db = get_db()
    like = f"%{query}%"
    if categoria_id:
        rows = db.execute(
            """SELECT titulo, conteudo, tags FROM kb_articles
               WHERE (titulo LIKE ? OR conteudo LIKE ? OR tags LIKE ?)
                 AND publico = 1
                 AND (categoria_id = ? OR categoria_id IS NULL)
               LIMIT 3""",
            (like, like, like, categoria_id),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT titulo, conteudo, tags FROM kb_articles
               WHERE (titulo LIKE ? OR conteudo LIKE ? OR tags LIKE ?)
                 AND publico = 1
               LIMIT 3""",
            (like, like, like),
        ).fetchall()

    if not rows:
        return "Nenhum artigo encontrado na base de conhecimento."

    results = []
    for r in rows:
        results.append(f"**{r['titulo']}**\n{(r['conteudo'] or '')[:400]}")
    return "\n\n---\n\n".join(results)


def buscar_tickets_similares(query: str, categoria_id: int = None, limit: int = 3) -> str:
    """Busca tickets similares já resolvidos para referência."""
    db = get_db()
    like = f"%{query}%"
    if categoria_id:
        rows = db.execute(
            """SELECT t.numero_chamado, t.titulo, t.descricao,
                      (SELECT tl.detalhe FROM ticket_log tl
                       WHERE tl.ticket_id = t.id AND tl.evento = 'FINALIZADO'
                       ORDER BY tl.criado_em DESC LIMIT 1) as resolucao
               FROM tickets t
               WHERE t.status = 'CONCLUIDO'
                 AND (t.titulo LIKE ? OR t.descricao LIKE ?)
                 AND t.categoria_id = ?
               ORDER BY t.criado_em DESC
               LIMIT ?""",
            (like, like, categoria_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT t.numero_chamado, t.titulo, t.descricao,
                      (SELECT tl.detalhe FROM ticket_log tl
                       WHERE tl.ticket_id = t.id AND tl.evento = 'FINALIZADO'
                       ORDER BY tl.criado_em DESC LIMIT 1) as resolucao
               FROM tickets t
               WHERE t.status = 'CONCLUIDO'
                 AND (t.titulo LIKE ? OR t.descricao LIKE ?)
               ORDER BY t.criado_em DESC
               LIMIT ?""",
            (like, like, limit),
        ).fetchall()

    if not rows:
        return "Nenhum ticket similar encontrado."

    results = []
    for r in rows:
        results.append(
            f"**{r['numero_chamado']} — {r['titulo']}**\n"
            f"Problema: {(r['descricao'] or '')[:200]}\n"
            f"Resolução: {(r['resolucao'] or 'Não documentada')[:300]}"
        )
    return "\n\n---\n\n".join(results)


def buscar_checklist_categoria(categoria_id: int) -> str:
    """Retorna o checklist padrão configurado para uma categoria."""
    import json as _json

    db = get_db()
    row = db.execute(
        "SELECT nome, checklist_padrao FROM categories WHERE id = ?",
        (categoria_id,),
    ).fetchone()

    if not row:
        return "Categoria não encontrada."

    try:
        items = _json.loads(row["checklist_padrao"] or "[]")
    except Exception:
        items = []

    if not items:
        return f"Categoria '{row['nome']}' não possui checklist padrão definido."

    return f"Checklist padrão de '{row['nome']}':\n" + "\n".join(f"- {i}" for i in items)


# ── Definições JSON das ferramentas para a Claude API ──────────────────────────

DIAGNOSTIC_TOOLS = [
    {
        "name": "buscar_kb",
        "description": (
            "Busca artigos na base de conhecimento do service desk usando palavras-chave. "
            "Use para encontrar soluções documentadas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Palavras-chave para busca (ex: 'VPN não conecta', 'impressora offline')",
                },
                "categoria_id": {
                    "type": "integer",
                    "description": "ID da categoria para filtrar resultados (opcional)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "buscar_tickets_similares",
        "description": (
            "Busca chamados similares já resolvidos. "
            "Use para encontrar soluções aplicadas anteriormente a problemas parecidos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Descrição do problema para busca",
                },
                "categoria_id": {
                    "type": "integer",
                    "description": "ID da categoria para filtrar (opcional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Máximo de resultados (padrão: 3)",
                },
            },
            "required": ["query"],
        },
    },
]

CHECKLIST_TOOLS = [
    {
        "name": "buscar_checklist_categoria",
        "description": "Retorna o checklist padrão de atendimento configurado para uma categoria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "categoria_id": {
                    "type": "integer",
                    "description": "ID da categoria do chamado",
                },
            },
            "required": ["categoria_id"],
        },
    },
]


def execute_tool(name: str, inputs: dict) -> str:
    """Executa uma ferramenta pelo nome e retorna o resultado como string."""
    if name == "buscar_kb":
        return buscar_kb(inputs["query"], inputs.get("categoria_id"))
    if name == "buscar_tickets_similares":
        return buscar_tickets_similares(
            inputs["query"],
            inputs.get("categoria_id"),
            inputs.get("limit", 3),
        )
    if name == "buscar_checklist_categoria":
        return buscar_checklist_categoria(inputs["categoria_id"])
    return f"Ferramenta '{name}' desconhecida."
