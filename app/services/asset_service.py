from datetime import datetime
from app.db import get_db

ASSET_TYPES = ["NOTEBOOK", "DESKTOP", "MONITOR", "CELULAR", "ACESSORIO", "OUTRO"]
ASSET_STATUSES = ["EM_USO", "ESTOQUE", "EM_MANUTENCAO", "EM_TRANSITO", "DESCARTADO"]

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def clean(v):
    return (v or "").strip()

def log_asset_event(asset_id: int, evento: str, detalhe: str = ""):
    db = get_db()
    db.execute(
        "INSERT INTO asset_history (asset_id, evento, detalhe, criado_em) VALUES (?, ?, ?, ?)",
        (asset_id, evento, detalhe, now())
    )
    db.commit()

def list_assets(filters=None):
    filters = filters or {}
    db = get_db()
    q = """SELECT id, tag, tipo, modelo, serial_number, local_base, responsavel, status, atualizado_em
             FROM assets WHERE 1=1"""
    params = []
    text = clean(filters.get("q"))
    if text:
        like = f"%{text}%"
        q += " AND (tag LIKE ? OR modelo LIKE ? OR serial_number LIKE ? OR local_base LIKE ? OR responsavel LIKE ?)"
        params.extend([like, like, like, like, like])
    status = clean(filters.get("status"))
    if status:
        q += " AND status=?"
        params.append(status)
    tipo = clean(filters.get("tipo"))
    if tipo:
        q += " AND tipo=?"
        params.append(tipo)
    q += " ORDER BY atualizado_em DESC, id DESC"
    return db.execute(q, params).fetchall()

def list_assets_for_select():
    return get_db().execute("SELECT id, tag, tipo, modelo, status FROM assets ORDER BY tag ASC").fetchall()

def get_asset(asset_id: int):
    return get_db().execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()

def create_asset(data):
    tag = clean(data.get("tag"))
    tipo = clean(data.get("tipo")).upper()
    modelo = clean(data.get("modelo"))
    serial_number = clean(data.get("serial_number"))
    local_base = clean(data.get("local_base"))
    responsavel = clean(data.get("responsavel"))
    status = clean(data.get("status")).upper()
    observacoes = clean(data.get("observacoes"))

    if not tag:
        raise ValueError("Tag do ativo é obrigatória.")
    if tipo not in ASSET_TYPES:
        raise ValueError("Tipo de ativo inválido.")
    if not modelo:
        raise ValueError("Modelo é obrigatório.")
    if status not in ASSET_STATUSES:
        raise ValueError("Status do ativo inválido.")

    db = get_db()
    t = now()
    cur = db.execute(
        """INSERT INTO assets (tag, tipo, modelo, serial_number, local_base, responsavel, status, observacoes, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tag, tipo, modelo, serial_number, local_base, responsavel, status, observacoes, t, t),
    )
    db.commit()
    asset_id = cur.lastrowid
    log_asset_event(asset_id, "CRIADO", f"Ativo criado com status {status}.")
    return asset_id

def update_asset(asset_id: int, data):
    old = get_asset(asset_id)
    if not old:
        raise ValueError("Ativo não encontrado.")

    tag = clean(data.get("tag"))
    tipo = clean(data.get("tipo")).upper()
    modelo = clean(data.get("modelo"))
    serial_number = clean(data.get("serial_number"))
    local_base = clean(data.get("local_base"))
    responsavel = clean(data.get("responsavel"))
    status = clean(data.get("status")).upper()
    observacoes = clean(data.get("observacoes"))

    if not tag:
        raise ValueError("Tag do ativo é obrigatória.")
    if tipo not in ASSET_TYPES:
        raise ValueError("Tipo de ativo inválido.")
    if not modelo:
        raise ValueError("Modelo é obrigatório.")
    if status not in ASSET_STATUSES:
        raise ValueError("Status do ativo inválido.")

    db = get_db()
    db.execute(
        """UPDATE assets
            SET tag=?, tipo=?, modelo=?, serial_number=?, local_base=?, responsavel=?, status=?, observacoes=?, atualizado_em=?
            WHERE id=?""",
        (tag, tipo, modelo, serial_number, local_base, responsavel, status, observacoes, now(), asset_id),
    )
    db.commit()

    changes = []
    for label, oldv, newv in [
        ("tag", old["tag"], tag),
        ("tipo", old["tipo"], tipo),
        ("modelo", old["modelo"], modelo),
        ("serial", old["serial_number"], serial_number),
        ("base/local", old["local_base"], local_base),
        ("responsável", old["responsavel"], responsavel),
        ("status", old["status"], status),
    ]:
        if (oldv or "") != (newv or ""):
            changes.append(f"{label}: '{oldv or '-'}' → '{newv or '-'}'")
    detail = "; ".join(changes) if changes else "Sem alterações relevantes."
    log_asset_event(asset_id, "EDITADO", detail)

def tickets_by_asset(asset_id: int):
    return get_db().execute(
        """SELECT id, tipo, titulo, prioridade, status, atualizado_em
            FROM tickets WHERE asset_id=? ORDER BY atualizado_em DESC""",
        (asset_id,),
    ).fetchall()

def get_asset_history(asset_id: int):
    return get_db().execute(
        "SELECT criado_em, evento, detalhe FROM asset_history WHERE asset_id=? ORDER BY criado_em DESC",
        (asset_id,)
    ).fetchall()

def asset_dashboard():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM assets").fetchone()["c"]
    by_status = {r["status"]: r["total"] for r in db.execute("SELECT status, COUNT(*) as total FROM assets GROUP BY status").fetchall()}
    by_tipo = {r["tipo"]: r["total"] for r in db.execute("SELECT tipo, COUNT(*) as total FROM assets GROUP BY tipo").fetchall()}
    return {"total": total, "by_status": by_status, "by_tipo": by_tipo}

def delete_asset(asset_id: int):
    db = get_db()
    # Desvincular chamados antes de deletar
    db.execute("UPDATE tickets SET asset_id=NULL WHERE asset_id=?", (asset_id,))
    db.execute("DELETE FROM asset_history WHERE asset_id=?", (asset_id,))
    db.execute("DELETE FROM entradas_nf_assets WHERE asset_id=?", (asset_id,))
    db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
    db.commit()
