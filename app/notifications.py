"""
Sistema de notificações internas.

Tipos:
  NOVO_CHAMADO       — novo chamado criado (para operadores da categoria)
  CHAMADO_ASSUMIDO   — chamado foi assumido (para quem abriu)
  STATUS_ATUALIZADO  — status mudou (para quem abriu)
  AGUARD_CONFIRMACAO — chamado aguarda confirmação (para quem abriu)
  CONCLUSAO_REJEITADA — solicitante rejeitou (para o operador responsável)
  CHAMADO_CONCLUIDO  — chamado concluído definitivamente (para ambos)
"""

from .db import get_db

def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def criar_notificacao(user_id: int, tipo: str, titulo: str, mensagem: str = "", ticket_id: int = None):
    """Cria uma notificação para um usuário."""
    if not user_id:
        return
    db = get_db()
    db.execute(
        "INSERT INTO notifications (user_id, tipo, titulo, mensagem, ticket_id, lida, criado_em) VALUES (?,?,?,?,?,0,?)",
        (user_id, tipo, titulo, mensagem or "", ticket_id, _now())
    )
    db.commit()


def notificar_operadores_categoria(categoria_id, tipo: str, titulo: str, mensagem: str = "", ticket_id: int = None, excluir_user_id: int = None):
    """Notifica todos os operadores atribuídos a uma categoria."""
    db = get_db()
    if categoria_id:
        rows = db.execute(
            """SELECT DISTINCT u.id FROM users u
               JOIN user_categories uc ON uc.user_id = u.id
               WHERE uc.category_id = ? AND u.active = 1 AND u.role IN ('operador','admin')""",
            (categoria_id,)
        ).fetchall()
    else:
        # sem categoria: notifica todos os operadores/admins
        rows = db.execute(
            "SELECT id FROM users WHERE active=1 AND role IN ('operador','admin')"
        ).fetchall()
    for r in rows:
        if excluir_user_id and r["id"] == excluir_user_id:
            continue
        criar_notificacao(r["id"], tipo, titulo, mensagem, ticket_id)


def notificar_admins(tipo: str, titulo: str, mensagem: str = "", ticket_id: int = None):
    """Notifica todos os admins."""
    db = get_db()
    rows = db.execute("SELECT id FROM users WHERE active=1 AND role='admin'").fetchall()
    for r in rows:
        criar_notificacao(r["id"], tipo, titulo, mensagem, ticket_id)


# ── Helpers de alto nível chamados pelos eventos do sistema ──────────────────

def on_ticket_criado(ticket_id: int, titulo: str, categoria_id, criado_por_id: int):
    """Dispara quando um novo chamado é criado."""
    notificar_operadores_categoria(
        categoria_id,
        tipo="NOVO_CHAMADO",
        titulo=f"Novo chamado: {titulo}",
        mensagem="Um novo chamado chegou na fila.",
        ticket_id=ticket_id,
        excluir_user_id=criado_por_id,
    )


def on_ticket_assumido(ticket_id: int, titulo: str, requester_user_id: int, operador_nome: str):
    """Dispara quando um operador assume o chamado."""
    criar_notificacao(
        requester_user_id,
        tipo="CHAMADO_ASSUMIDO",
        titulo=f"Chamado assumido: {titulo}",
        mensagem=f"{operador_nome} assumiu seu chamado e iniciou o atendimento.",
        ticket_id=ticket_id,
    )


def on_status_atualizado(ticket_id: int, titulo: str, requester_user_id: int, novo_status: str):
    """Dispara quando o status muda (exceto finalizações tratadas separadamente)."""
    if novo_status in ("AGUARDANDO_CONFIRMACAO", "CONCLUIDO"):
        return  # tratados por funções específicas
    criar_notificacao(
        requester_user_id,
        tipo="STATUS_ATUALIZADO",
        titulo=f"Chamado atualizado: {titulo}",
        mensagem=f"Status alterado para {novo_status.replace('_', ' ')}.",
        ticket_id=ticket_id,
    )


def on_aguardando_confirmacao(ticket_id: int, titulo: str, requester_user_id: int, operador_nome: str):
    """Dispara quando operador finaliza e aguarda confirmação."""
    criar_notificacao(
        requester_user_id,
        tipo="AGUARD_CONFIRMACAO",
        titulo=f"Confirme a conclusão: {titulo}",
        mensagem=f"{operador_nome} finalizou o atendimento. Confirme se o chamado foi resolvido.",
        ticket_id=ticket_id,
    )


def on_conclusao_rejeitada(ticket_id: int, titulo: str, assigned_user_id: int, solicitante_nome: str, motivo: str = ""):
    """Dispara quando solicitante rejeita a conclusão."""
    if not assigned_user_id:
        return
    msg = f"{solicitante_nome} rejeitou a conclusão."
    if motivo:
        msg += f" Motivo: {motivo}"
    criar_notificacao(
        assigned_user_id,
        tipo="CONCLUSAO_REJEITADA",
        titulo=f"Conclusão rejeitada: {titulo}",
        mensagem=msg,
        ticket_id=ticket_id,
    )


def on_chamado_concluido(ticket_id: int, titulo: str, requester_user_id: int, assigned_user_id: int, confirmado_por: str):
    """Dispara quando o chamado é concluído definitivamente."""
    # Notifica o operador que foi confirmado
    if assigned_user_id and assigned_user_id != requester_user_id:
        criar_notificacao(
            assigned_user_id,
            tipo="CHAMADO_CONCLUIDO",
            titulo=f"Chamado concluído: {titulo}",
            mensagem=f"{confirmado_por} confirmou a conclusão.",
            ticket_id=ticket_id,
        )


# ── Leitura ──────────────────────────────────────────────────────────────────

def get_notificacoes(user_id: int, apenas_nao_lidas: bool = False, limite: int = 30):
    db = get_db()
    q = "SELECT * FROM notifications WHERE user_id=?"
    params = [user_id]
    if apenas_nao_lidas:
        q += " AND lida=0"
    q += " ORDER BY criado_em DESC LIMIT ?"
    params.append(limite)
    return db.execute(q, params).fetchall()


def contar_nao_lidas(user_id: int) -> int:
    db = get_db()
    return db.execute(
        "SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND lida=0", (user_id,)
    ).fetchone()["c"]


def marcar_lida(notif_id: int, user_id: int):
    db = get_db()
    db.execute("UPDATE notifications SET lida=1 WHERE id=? AND user_id=?", (notif_id, user_id))
    db.commit()


def marcar_todas_lidas(user_id: int):
    db = get_db()
    db.execute("UPDATE notifications SET lida=1 WHERE user_id=?", (user_id,))
    db.commit()

def on_aprovacao_necessaria(ticket_id: int, titulo: str):
    """Notifica admins quando um chamado precisa de aprovação."""
    db = get_db()
    admins = db.execute("SELECT id FROM users WHERE active=1 AND role='admin'").fetchall()
    for a in admins:
        criar_notificacao(a["id"], "APROVACAO_NECESSARIA",
                          f"Aprovação necessária: {titulo}",
                          "Um chamado aguarda sua aprovação antes de iniciar.",
                          ticket_id)

def on_chamado_aprovado(ticket_id: int, titulo: str, requester_user_id: int, aprovador_nome: str):
    criar_notificacao(requester_user_id, "CHAMADO_APROVADO",
                      f"Chamado aprovado: {titulo}",
                      f"{aprovador_nome} aprovou seu chamado. Ele está agora na fila.",
                      ticket_id)

def on_chamado_reprovado(ticket_id: int, titulo: str, requester_user_id: int, aprovador_nome: str):
    criar_notificacao(requester_user_id, "CHAMADO_REPROVADO",
                      f"Chamado reprovado: {titulo}",
                      f"{aprovador_nome} reprovou seu chamado.",
                      ticket_id)

def on_transferencia(ticket_id: int, titulo: str, para_user_id: int, de_nome: str):
    criar_notificacao(para_user_id, "CHAMADO_TRANSFERIDO",
                      f"Chamado transferido para você: {titulo}",
                      f"Transferido por {de_nome}.",
                      ticket_id)
