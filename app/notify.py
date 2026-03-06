import smtplib
import threading
from email.message import EmailMessage
from typing import List


def send_email(host: str, port: int, user: str, password: str,
               mail_from: str, to: List[str], subject: str, body: str) -> bool:
    """Envia e-mail via SMTP. Retorna True se enviou, False se não havia config."""
    if not host or not to:
        return False
    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        try:
            smtp.starttls()
        except Exception:
            pass
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)
    return True


def _fire(host, port, user, password, mail_from, to, subject, body):
    """Disparo em background — não bloqueia a requisição."""
    try:
        send_email(host, port, user, password, mail_from, to, subject, body)
    except Exception:
        pass


def notify_async(app_config, to: List[str], subject: str, body: str):
    """Envia e-mail em thread separada usando a config do Flask."""
    t = threading.Thread(
        target=_fire,
        args=(
            app_config.get("SMTP_HOST", ""),
            app_config.get("SMTP_PORT", 587),
            app_config.get("SMTP_USER", ""),
            app_config.get("SMTP_PASS", ""),
            app_config.get("SMTP_FROM", "chamados@localhost"),
            to,
            subject,
            body,
        ),
        daemon=True,
    )
    t.start()


# ── Helpers de notificação por evento ────────────────────────────────────────

def notify_ticket_created(app_config, ticket_id: int, titulo: str,
                           solicitante: str, tipo: str):
    """Notifica os admins quando um chamado é aberto."""
    to = app_config.get("ALERT_TO_EMAILS") or []
    if not to:
        return
    subject = f"[Chamados] Novo chamado #{ticket_id} — {tipo}"
    body = (
        f"Um novo chamado foi aberto.\n\n"
        f"  ID       : #{ticket_id}\n"
        f"  Tipo     : {tipo}\n"
        f"  Título   : {titulo}\n"
        f"  Solicitante: {solicitante}\n\n"
        f"Acesse o sistema para visualizar e atribuir o chamado."
    )
    notify_async(app_config, to, subject, body)


def notify_ticket_assigned(app_config, ticket_id: int, titulo: str,
                            responsavel: str, requester_email: str | None):
    """Notifica o solicitante quando o chamado é assumido por um operador."""
    to = [requester_email] if requester_email else []
    to += app_config.get("ALERT_TO_EMAILS") or []
    if not to:
        return
    subject = f"[Chamados] Chamado #{ticket_id} foi assumido"
    body = (
        f"Seu chamado foi assumido e está em atendimento.\n\n"
        f"  ID         : #{ticket_id}\n"
        f"  Título     : {titulo}\n"
        f"  Responsável: {responsavel}\n\n"
        f"Acompanhe o andamento no sistema."
    )
    notify_async(app_config, to, subject, body)


def notify_status_changed(app_config, ticket_id: int, titulo: str,
                           new_status: str, requester_email: str | None):
    """Notifica o solicitante quando o status do chamado muda."""
    to = [requester_email] if requester_email else []
    if not to:
        return
    subject = f"[Chamados] Status atualizado — #{ticket_id}"
    body = (
        f"O status do seu chamado foi atualizado.\n\n"
        f"  ID     : #{ticket_id}\n"
        f"  Título : {titulo}\n"
        f"  Status : {new_status}\n\n"
        f"Acesse o sistema para mais detalhes."
    )
    notify_async(app_config, to, subject, body)
