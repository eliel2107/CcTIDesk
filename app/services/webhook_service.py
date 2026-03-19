"""Serviço de Webhooks."""

import ipaddress
import json as _json
import hmac
import hashlib
import re
import threading
import logging
from urllib.parse import urlparse

from app.db import get_db
from app.helpers import _now

_logger = logging.getLogger(__name__)

# Padrões de host bloqueados para prevenir SSRF
_BLOCKED_HOSTS = re.compile(
    r"^(localhost|127\.|::1|0\.0\.0\.0|169\.254\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)",
    re.IGNORECASE,
)


def _validate_webhook_url(url: str) -> None:
    """Valida URL de webhook bloqueando hosts internos/privados (SSRF)."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("URL de webhook inválida.")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL de webhook deve usar http ou https.")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("URL de webhook sem host válido.")
    if _BLOCKED_HOSTS.match(host):
        raise ValueError(f"URL de webhook aponta para endereço interno bloqueado: {host}")
    # Bloqueia IPs privados via ipaddress
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError(f"URL de webhook aponta para IP não-público: {host}")
    except ValueError as e:
        if "aponta para" in str(e):
            raise
    # hostname não é IP — prossegue (não resolve DNS aqui para evitar latência)


def list_webhooks():
    return get_db().execute("SELECT * FROM webhooks ORDER BY nome").fetchall()


def create_webhook(nome: str, url: str, eventos: list, secret: str = "") -> int:
    _validate_webhook_url(url)
    db = get_db()
    cur = db.execute(
        "INSERT INTO webhooks (nome, url, eventos, ativo, secret, criado_em) VALUES (?,?,?,1,?,?)",
        (nome, url, _json.dumps(eventos), secret, _now())
    )
    db.commit()
    return cur.lastrowid


def update_webhook(webhook_id: int, nome: str, url: str, eventos: list, ativo: bool, secret: str = ""):
    _validate_webhook_url(url)
    db = get_db()
    db.execute(
        "UPDATE webhooks SET nome=?, url=?, eventos=?, ativo=?, secret=? WHERE id=?",
        (nome, url, _json.dumps(eventos), 1 if ativo else 0, secret, webhook_id)
    )
    db.commit()


def delete_webhook(webhook_id: int):
    db = get_db()
    db.execute("DELETE FROM webhooks WHERE id=?", (webhook_id,))
    db.commit()


def fire_webhooks(evento: str, payload: dict):
    """Dispara webhooks ativos que escutam o evento."""
    try:
        rows = get_db().execute(
            "SELECT * FROM webhooks WHERE ativo=1 AND eventos LIKE ?", (f"%{evento}%",)
        ).fetchall()
    except Exception:
        _logger.exception("Erro ao consultar webhooks ativos.")
        return
    for row in rows:
        try:
            evts = _json.loads(row["eventos"])
        except Exception:
            evts = []
        if evento not in evts:
            continue
        body = _json.dumps({"evento": evento, **payload}, default=str, ensure_ascii=False)

        def _send(url, body, secret):
            try:
                import urllib.request
                headers = {"Content-Type": "application/json"}
                if secret:
                    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
                    headers["X-CCTI-Signature"] = sig
                req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                _logger.warning(f"Falha ao enviar webhook para {url}")

        threading.Thread(target=_send, args=(row["url"], body, row["secret"] or ""), daemon=True).start()
