import sqlite3
from flask import current_app, g

SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descricao TEXT,
    solicitante TEXT,
    prioridade TEXT NOT NULL,
    status TEXT NOT NULL,
    responsavel TEXT,
    fornecedor TEXT,
    centro_custo TEXT,
    valor_estimado REAL,
    link_pedido TEXT,
    codigo_rastreio TEXT,
    data_limite TEXT,
    destinatario TEXT,
    telefone TEXT,
    endereco TEXT,
    cidade TEXT,
    estado TEXT,
    cep TEXT,
    asset_id INTEGER,
    requester_user_id INTEGER,
    assigned_user_id INTEGER,
    closed_em TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY(asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS ticket_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    evento TEXT NOT NULL,
    detalhe TEXT,
    criado_em TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    stored_name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    uploaded_em TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS ticket_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    step_text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    done_em TEXT,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    active INTEGER NOT NULL DEFAULT 1,
    created_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    modelo TEXT NOT NULL,
    serial_number TEXT,
    local_base TEXT,
    responsavel TEXT,
    status TEXT NOT NULL,
    observacoes TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    evento TEXT NOT NULL,
    detalhe TEXT,
    criado_em TEXT NOT NULL,
    FOREIGN KEY(asset_id) REFERENCES assets(id)
);
"""


MIGRATIONS = [
    ("responsavel", "ALTER TABLE tickets ADD COLUMN responsavel TEXT"),
    ("fornecedor", "ALTER TABLE tickets ADD COLUMN fornecedor TEXT"),
    ("centro_custo", "ALTER TABLE tickets ADD COLUMN centro_custo TEXT"),
    ("valor_estimado", "ALTER TABLE tickets ADD COLUMN valor_estimado REAL"),
    ("link_pedido", "ALTER TABLE tickets ADD COLUMN link_pedido TEXT"),
    ("codigo_rastreio", "ALTER TABLE tickets ADD COLUMN codigo_rastreio TEXT"),
    ("data_limite", "ALTER TABLE tickets ADD COLUMN data_limite TEXT"),
    ("destinatario", "ALTER TABLE tickets ADD COLUMN destinatario TEXT"),
    ("telefone", "ALTER TABLE tickets ADD COLUMN telefone TEXT"),
    ("endereco", "ALTER TABLE tickets ADD COLUMN endereco TEXT"),
    ("cidade", "ALTER TABLE tickets ADD COLUMN cidade TEXT"),
    ("estado", "ALTER TABLE tickets ADD COLUMN estado TEXT"),
    ("cep", "ALTER TABLE tickets ADD COLUMN cep TEXT"),
    ("asset_id", "ALTER TABLE tickets ADD COLUMN asset_id INTEGER"),
    ("closed_em", "ALTER TABLE tickets ADD COLUMN closed_em TEXT"),
    ("requester_user_id", "ALTER TABLE tickets ADD COLUMN requester_user_id INTEGER"),
    ("assigned_user_id", "ALTER TABLE tickets ADD COLUMN assigned_user_id INTEGER"),
]
USER_MIGRATIONS = [
    ("active", "ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1"),
]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def _columns_in_table(db, table_name: str):
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r["name"] for r in rows}

def _table_exists(db, table_name: str) -> bool:
    r = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    return r is not None

def migrate_db():
    db = get_db()
    cols = _columns_in_table(db, "tickets")
    for col, sql in MIGRATIONS:
        if col not in cols:
            db.execute(sql)

    if _table_exists(db, "users"):
        ucols = _columns_in_table(db, "users")
        for col, sql in USER_MIGRATIONS:
            if col not in ucols:
                db.execute(sql)

    if not _table_exists(db, "attachments"):
        db.execute("""        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            stored_name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER,
            uploaded_em TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id)
        );""")

    if not _table_exists(db, "ticket_steps"):
        db.execute("""        CREATE TABLE IF NOT EXISTS ticket_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            step_text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            done_em TEXT,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id)
        );""")

    if not _table_exists(db, "users"):
        db.execute("""        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            active INTEGER NOT NULL DEFAULT 1,
            created_em TEXT NOT NULL
        );""")

    if not _table_exists(db, "assets"):
        db.execute("""        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL UNIQUE,
            tipo TEXT NOT NULL,
            modelo TEXT NOT NULL,
            serial_number TEXT,
            local_base TEXT,
            responsavel TEXT,
            status TEXT NOT NULL,
            observacoes TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );""")

    if not _table_exists(db, "asset_history"):
        db.execute("""        CREATE TABLE IF NOT EXISTS asset_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            evento TEXT NOT NULL,
            detalhe TEXT,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(asset_id) REFERENCES assets(id)
        );""")

    db.commit()

def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()
    migrate_db()

def init_app(app):
    app.teardown_appcontext(close_db)
