import click
from flask import Flask
from .db import init_db
from .models import seed_example, get_overdue_tickets
from .notify import send_email

def init_cli(app: Flask):
    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        click.echo("Banco inicializado/migrado com sucesso.")

    @app.cli.command("seed")
    def seed_command():
        init_db()
        seed_example()
        click.echo("Dados de exemplo inseridos.")

    @app.cli.command("notify")
    def notify_command():
        """Envia e-mail com lista de chamados atrasados (se SMTP configurado)."""
        init_db()
        overdue = get_overdue_tickets()
        if not overdue:
            click.echo("Nenhum chamado atrasado.")
            return

        to = app.config.get("ALERT_TO_EMAILS") or []
        if not to or not app.config.get("SMTP_HOST"):
            click.echo("Atrasados encontrados, mas SMTP/ALERT_TO_EMAILS não configurado. (Veja .env.example)")
            for r in overdue:
                click.echo(f"#{r['id']} {r['data_limite']} {r['status']} {r['titulo']} ({r['responsavel'] or '-'})")
            return

        lines = ["Chamados atrasados:", ""]
        for r in overdue:
            lines.append(f"- #{r['id']} ({r['tipo']}) {r['titulo']} | Resp: {r['responsavel'] or '-'} | {r['status']} | Limite: {r['data_limite']}")
        body = "\n".join(lines)

        ok = send_email(
            host=app.config["SMTP_HOST"],
            port=app.config["SMTP_PORT"],
            user=app.config["SMTP_USER"],
            password=app.config["SMTP_PASS"],
            mail_from=app.config["SMTP_FROM"],
            to=to,
            subject="⚠️ Chamados atrasados - Compras & Envio",
            body=body,
        )
        click.echo("E-mail enviado." if ok else "Não foi possível enviar (SMTP não configurado).")
