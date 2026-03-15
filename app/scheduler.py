"""
Jobs agendados: backup automático, digest diário por e-mail, chamados recorrentes.
"""
import os
import shutil
import sqlite3
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP
# ══════════════════════════════════════════════════════════════════════════════

def run_backup(app):
    """Copia o banco SQLite para a pasta de backups e limpa cópias antigas."""
    try:
        db_path   = app.config["DATABASE"]
        backup_dir = app.config.get("BACKUP_DIR", os.path.join(os.getcwd(), "instance", "backups"))
        keep_days  = int(app.config.get("BACKUP_KEEP_DAYS", 30))

        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest  = os.path.join(backup_dir, f"chamados_{stamp}.db")

        # Usa a API de backup do SQLite para consistência mesmo com WAL
        src  = sqlite3.connect(db_path)
        bkp  = sqlite3.connect(dest)
        src.backup(bkp)
        bkp.close()
        src.close()

        logger.info(f"[Backup] Salvo em {dest}")

        # Remove backups mais antigos que keep_days
        cutoff = datetime.now() - timedelta(days=keep_days)
        removed = 0
        for fname in os.listdir(backup_dir):
            if not fname.endswith(".db"):
                continue
            fpath = os.path.join(backup_dir, fname)
            if datetime.fromtimestamp(os.path.getmtime(fpath)) < cutoff:
                os.remove(fpath)
                removed += 1
        if removed:
            logger.info(f"[Backup] {removed} arquivo(s) antigo(s) removido(s).")
    except Exception:
        logger.exception("[Backup] Erro ao executar backup.")


# ══════════════════════════════════════════════════════════════════════════════
# DIGEST DIÁRIO
# ══════════════════════════════════════════════════════════════════════════════

def run_daily_digest(app):
    """Envia e-mail de resumo diário para os admins com situação dos chamados."""
    try:
        from .db import get_db
        from .notify import notify_async

        smtp_host = app.config.get("SMTP_HOST", "")
        alert_to  = app.config.get("ALERT_TO_EMAILS", [])
        if not smtp_host or not alert_to:
            return  # SMTP não configurado

        db = get_db()
        today = datetime.now().strftime("%Y-%m-%d")

        novos     = db.execute("SELECT COUNT(*) FROM tickets WHERE substr(criado_em,1,10)=?", (today,)).fetchone()[0]
        abertos   = db.execute("SELECT COUNT(*) FROM tickets WHERE status='ABERTO'").fetchone()[0]
        em_and    = db.execute("SELECT COUNT(*) FROM tickets WHERE status='EM_ANDAMENTO'").fetchone()[0]
        aguard    = db.execute("SELECT COUNT(*) FROM tickets WHERE status='AGUARDANDO_CONFIRMACAO'").fetchone()[0]
        info      = db.execute("SELECT COUNT(*) FROM tickets WHERE status='AGUARDANDO_INFO'").fetchone()[0]
        atrasados = db.execute(
            "SELECT COUNT(*) FROM tickets WHERE data_limite < ? AND status NOT IN ('CONCLUIDO','CANCELADO')",
            (today,)
        ).fetchone()[0]
        urgentes  = db.execute(
            "SELECT COUNT(*) FROM tickets WHERE prioridade='URGENTE' AND status NOT IN ('CONCLUIDO','CANCELADO')"
        ).fetchone()[0]

        # Chamados urgentes abertos — lista curta
        urg_rows = db.execute(
            "SELECT numero_chamado, titulo, responsavel, status FROM tickets "
            "WHERE prioridade='URGENTE' AND status NOT IN ('CONCLUIDO','CANCELADO') "
            "ORDER BY criado_em ASC LIMIT 10"
        ).fetchall()

        app_url = app.config.get("APP_URL", "")
        lines = [
            f"📊 RESUMO DIÁRIO — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "─" * 48,
            f"  Novos hoje          : {novos}",
            f"  Abertos (fila)      : {abertos}",
            f"  Em andamento        : {em_and}",
            f"  Aguardando confirm. : {aguard}",
            f"  Aguardando info     : {info}",
            f"  Atrasados           : {atrasados}",
            f"  Urgentes ativos     : {urgentes}",
            "",
        ]

        if urg_rows:
            lines.append("🚨 URGENTES EM ABERTO:")
            for r in urg_rows:
                lines.append(f"  [{r['numero_chamado'] or '?'}] {r['titulo']} — {r['status'].replace('_',' ')} — {r['responsavel'] or 'Sem responsável'}")
            lines.append("")

        if app_url:
            lines.append(f"🔗 Acesse: {app_url}/dashboard")

        body = "\n".join(lines)
        notify_async(dict(app.config), alert_to, f"[CCTI] Resumo diário — {datetime.now().strftime('%d/%m/%Y')}", body)
        logger.info("[Digest] E-mail de resumo enviado.")
    except Exception:
        logger.exception("[Digest] Erro ao enviar digest diário.")


# ══════════════════════════════════════════════════════════════════════════════
# CHAMADOS RECORRENTES
# ══════════════════════════════════════════════════════════════════════════════

def run_recurring_tickets():
    """Cria chamados recorrentes conforme configuração em recurring_tickets."""
    try:
        from .db import get_db
        from .models import create_ticket, _now

        db = get_db()
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        schedules = db.execute(
            "SELECT * FROM recurring_tickets WHERE ativo=1"
        ).fetchall()

        for sch in schedules:
            # Verifica se deve criar hoje
            freq  = sch["frequencia"]  # "diario", "semanal", "mensal"
            dia   = sch["dia_execucao"]  # int: dia do mês ou dia da semana (0=seg)
            hora  = sch["hora_execucao"] or "08:00"

            # Verificar se já foi criado hoje
            last = db.execute(
                "SELECT MAX(criado_em) FROM tickets WHERE titulo=? AND substr(criado_em,1,10)=?",
                (sch["titulo"], today_str)
            ).fetchone()[0]
            if last:
                continue  # já criou hoje

            deve_criar = False
            if freq == "diario":
                deve_criar = True
            elif freq == "semanal" and now.weekday() == int(dia or 0):
                deve_criar = True
            elif freq == "mensal" and now.day == int(dia or 1):
                deve_criar = True

            if not deve_criar:
                continue

            # Hora de execução
            hora_prog = int(hora.split(":")[0])
            if now.hour < hora_prog:
                continue  # ainda não chegou a hora

            try:
                data = json.loads(sch["ticket_data"] or "{}")
                data["titulo"] = sch["titulo"]
                if not data.get("solicitante"):
                    data["solicitante"] = "Sistema (Recorrente)"
                if not data.get("prioridade"):
                    data["prioridade"] = "MEDIA"
                tid = create_ticket(data)
                db.execute(
                    "UPDATE recurring_tickets SET ultima_execucao=? WHERE id=?",
                    (_now(), sch["id"])
                )
                db.commit()
                logger.info(f"[Recorrente] Chamado #{tid} criado: {sch['titulo']}")
            except Exception as e:
                logger.error(f"[Recorrente] Erro ao criar '{sch['titulo']}': {e}")
    except Exception:
        logger.exception("[Recorrente] Erro no job de chamados recorrentes.")


def run_assignment_timeout_fallback(app):
    """Autoatribui chamados sem responsável após o prazo de aceite."""
    try:
        if not app.config.get('ASSIGNMENT_AUTO_FALLBACK_ENABLED', True):
            return 0
        from .models import auto_assign_overdue_tickets
        processed = auto_assign_overdue_tickets(app.config.get('ASSIGNMENT_TIMEOUT_MINUTES', 15))
        if processed:
            logger.info(f"[Fila] {processed} chamado(s) autoatribuído(s) por timeout de assunção.")
        return processed
    except Exception:
        logger.exception('[Fila] Erro ao executar fallback de assunção.')
        return 0


def run_nf_cleanup(app):
    try:
        from .services.nf_service import cleanup_expired_cancelled_drafts
        removed = cleanup_expired_cancelled_drafts()
        if removed:
            logger.info(f"[NF] {removed} rascunho(s) cancelado(s) expirado(s) removido(s).")
        return removed
    except Exception:
        logger.exception("[NF] Erro ao limpar rascunhos cancelados expirados.")
        return 0
