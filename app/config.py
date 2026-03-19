import os
import warnings

class Config:
    def __init__(self):
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.DATABASE = os.path.join(os.getcwd(), "instance", "chamados.db")
        self.UPLOAD_FOLDER = os.path.join(os.getcwd(), "instance", "uploads")
        self.MAX_CONTENT_LENGTH = 10 * 1024 * 1024
        self.ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
        self.MAX_ATTACHMENTS_PER_TYPE = {"COMPRA": 20, "ENVIO": 30}

        # SMTP
        self.SMTP_HOST = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
        self.SMTP_USER = os.getenv("SMTP_USER", "")
        self.SMTP_PASS = os.getenv("SMTP_PASS", "")
        self.SMTP_FROM = os.getenv("SMTP_FROM", "chamados@localhost")
        self.ALERT_TO_EMAILS = [e.strip() for e in (os.getenv("ALERT_TO_EMAILS", "") or "").split(",") if e.strip()]

        # Admin padrão
        self.ADMIN_DEFAULT_EMAIL = os.getenv("ADMIN_DEFAULT_EMAIL", "admin@local")
        self.ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")

        # ── CSRF ─────────────────────────────────────────────────────────
        self.WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").lower() != "false"
        self.WTF_CSRF_TIME_LIMIT = 3600

        # ── Rate Limiting ─────────────────────────────────────────────────
        self.RATELIMIT_DEFAULT = "300 per hour"
        self.RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
        self.RATELIMIT_HEADERS_ENABLED = True
        self.RATELIMIT_STRATEGY = "fixed-window"

        # ── Sentry ────────────────────────────────────────────────────────
        self.SENTRY_DSN = os.getenv("SENTRY_DSN", "")

        # ── Backup ───────────────────────────────────────────────────────
        self.BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.getcwd(), "instance", "backups"))
        self.BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "30"))

        # ── App URL (usado em e-mails e portais externos) ─────────────────
        self.APP_URL = os.getenv("APP_URL", "http://localhost:5000")

        # ── IA Assistida ────────────────────────────────────────────────────
        self.AI_ASSIST_ENABLED = os.getenv("AI_ASSIST_ENABLED", "false").lower() == "true"
        self.AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
        self.AI_API_KEY = os.getenv("AI_API_KEY", "")
        self.AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")
        self.AI_BASE_URL = os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        self.AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30") or "30")
        self.AI_MAX_CONTEXT_CHARS = int(os.getenv("AI_MAX_CONTEXT_CHARS", "6000") or "6000")

        # ── Time de Agentes Claude (operator-assist) ────────────────────────────
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

        # ── Fila / assunção com timeout ───────────────────────────────────────
        self.ASSIGNMENT_AUTO_FALLBACK_ENABLED = os.getenv("ASSIGNMENT_AUTO_FALLBACK_ENABLED", "true").lower() == "true"
        self.ASSIGNMENT_TIMEOUT_MINUTES = int(os.getenv("ASSIGNMENT_TIMEOUT_MINUTES", "15") or "15")

        # ── NF / rascunhos ───────────────────────────────────────────────────
        self.NF_CANCELLED_DRAFT_RETENTION_DAYS = int(os.getenv("NF_CANCELLED_DRAFT_RETENTION_DAYS", "15") or "15")
        self.NF_DRAFT_MAX_AGE_DAYS = int(os.getenv("NF_DRAFT_MAX_AGE_DAYS", "30") or "30")

        # ── Regras de negócio V16 ─────────────────────────────────────────────
        self.TICKET_REOPEN_WINDOW_HOURS = int(os.getenv("TICKET_REOPEN_WINDOW_HOURS", "48") or "48")

        # ── Sessão ─────────────────────────────────────────────────────────
        from datetime import timedelta
        self.PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8") or "8"))
        self.SESSION_REFRESH_EACH_REQUEST = True

        self._validate()

    def _validate(self):
        """Emite avisos se variáveis críticas estão com valores padrão inseguros."""
        env = os.getenv("FLASK_ENV", "production")
        if env == "production":
            if self.SECRET_KEY == "dev-secret-change-me":
                warnings.warn(
                    "⚠️  SECRET_KEY está com valor padrão inseguro. "
                    "Defina a variável de ambiente SECRET_KEY antes de colocar em produção.",
                    stacklevel=2
                )
            if self.ADMIN_DEFAULT_PASSWORD == "admin123":
                warnings.warn(
                    "⚠️  ADMIN_DEFAULT_PASSWORD está com valor padrão. "
                    "Defina ADMIN_DEFAULT_PASSWORD no ambiente.",
                    stacklevel=2
                )
