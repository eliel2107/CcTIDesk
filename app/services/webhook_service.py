"""Serviço de Webhooks."""

import json as _json
import hmac
import hashlib
import threading
import logging

from app.db import get_db
from app.helpers import _now

_logger = logging.getLogger(__name__)


def list_webhooks():
    return get_db().execute("SELECT * FROM webhooks ORDER BY nome").fetchall()


def create_webhook(nome: str, url: str, eventos: list, secret: str = "") -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO webhooks (nome, url, eventos, ativo, secret, criado_em) VALUES (?,?,?,1,?,?)",
        (nome, url, _json.dumps(eventos), secret, _now())
    )
    db.commit()
    return cur.lastrowid


def update_webhook(webhook_id: int, nome: str, url: str, eventos: list, ativo: bool, secret: str = ""):
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
