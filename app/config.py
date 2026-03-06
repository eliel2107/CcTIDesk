import os

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

        # ── CSRF (Flask-WTF) ──────────────────────────────────────────────
        # Em testes, defina WTF_CSRF_ENABLED=False para desabilitar
        self.WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").lower() != "false"
        self.WTF_CSRF_TIME_LIMIT = 3600  # token expira em 1h

        # ── Rate Limiting (flask-limiter) ─────────────────────────────────
        # Storage em memória por padrão; troque por Redis em produção:
        # RATELIMIT_STORAGE_URI = "redis://localhost:6379"
        self.RATELIMIT_DEFAULT = "300 per hour"
        self.RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
        self.RATELIMIT_HEADERS_ENABLED = True   # expõe X-RateLimit-* headers
        self.RATELIMIT_STRATEGY = "fixed-window"
