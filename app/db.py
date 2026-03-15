import sqlite3
from flask import current_app, g

SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT,
    cor TEXT NOT NULL DEFAULT '#6366f1',
    ativo INTEGER NOT NULL DEFAULT 1,
    campos_visiveis TEXT,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_categories (
    user_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, category_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    classificacao TEXT NOT NULL DEFAULT 'REQUISICAO',
    numero_chamado TEXT,
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
    categoria_id INTEGER,
    closed_em TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY(asset_id) REFERENCES assets(id),
    FOREIGN KEY(categoria_id) REFERENCES categories(id)
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
    ("categoria_id", "ALTER TABLE tickets ADD COLUMN categoria_id INTEGER"),
    ("classificacao", "ALTER TABLE tickets ADD COLUMN classificacao TEXT NOT NULL DEFAULT 'REQUISICAO'"),
    ("numero_chamado", "ALTER TABLE tickets ADD COLUMN numero_chamado TEXT"),
    # Novas melhorias
    ("sla_deadline", "ALTER TABLE tickets ADD COLUMN sla_deadline TEXT"),
    ("aprovado_por", "ALTER TABLE tickets ADD COLUMN aprovado_por TEXT"),
    ("aprovado_em", "ALTER TABLE tickets ADD COLUMN aprovado_em TEXT"),
    ("aprovador_user_id", "ALTER TABLE tickets ADD COLUMN aprovador_user_id INTEGER"),
    ("reaberto_em", "ALTER TABLE tickets ADD COLUMN reaberto_em TEXT"),
    ("tma_minutos", "ALTER TABLE tickets ADD COLUMN tma_minutos INTEGER"),
    ("motivo_devolucao", "ALTER TABLE tickets ADD COLUMN motivo_devolucao TEXT"),
]
USER_MIGRATIONS = [
    ("active", "ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1"),
]
CATEGORY_MIGRATIONS = [
    ("campos_visiveis", "ALTER TABLE categories ADD COLUMN campos_visiveis TEXT"),
    ("sla_horas", "ALTER TABLE categories ADD COLUMN sla_horas INTEGER"),
    ("checklist_padrao", "ALTER TABLE categories ADD COLUMN checklist_padrao TEXT"),
    ("template_descricao", "ALTER TABLE categories ADD COLUMN template_descricao TEXT"),
    ("requer_aprovacao", "ALTER TABLE categories ADD COLUMN requer_aprovacao INTEGER NOT NULL DEFAULT 0"),
    ("valor_aprovacao_limite", "ALTER TABLE categories ADD COLUMN valor_aprovacao_limite REAL"),
]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA synchronous=NORMAL")
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

    if not _table_exists(db, "categories"):
        db.execute("""CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT,
            cor TEXT NOT NULL DEFAULT '#6366f1',
            ativo INTEGER NOT NULL DEFAULT 1,
            campos_visiveis TEXT,
            sla_horas INTEGER,
            checklist_padrao TEXT,
            template_descricao TEXT,
            requer_aprovacao INTEGER NOT NULL DEFAULT 0,
            valor_aprovacao_limite REAL,
            criado_em TEXT NOT NULL
        );""")
    else:
        ccols = _columns_in_table(db, "categories")
        for col, sql in CATEGORY_MIGRATIONS:
            if col not in ccols:
                db.execute(sql)

    if not _table_exists(db, "user_categories"):
        db.execute("""CREATE TABLE IF NOT EXISTS user_categories (
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, category_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
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

    if not _table_exists(db, "notifications"):
        db.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            mensagem TEXT,
            ticket_id INTEGER,
            lida INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        );""")

    # Comentários / notas internas
    if not _table_exists(db, "ticket_comments"):
        db.execute("""CREATE TABLE IF NOT EXISTS ticket_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_nome TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            interno INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );""")

    # Transferências de chamado
    if not _table_exists(db, "ticket_transfers"):
        db.execute("""CREATE TABLE IF NOT EXISTS ticket_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            de_user_id INTEGER,
            de_user_nome TEXT,
            para_user_id INTEGER NOT NULL,
            para_user_nome TEXT NOT NULL,
            motivo TEXT,
            transferido_em TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        );""")

    # Grupos de operadores
    if not _table_exists(db, "operator_groups"):
        db.execute("""CREATE TABLE IF NOT EXISTS operator_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT,
            cor TEXT NOT NULL DEFAULT '#6366f1',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        );""")

    if not _table_exists(db, "group_members"):
        db.execute("""CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY(group_id) REFERENCES operator_groups(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );""")

    if not _table_exists(db, "group_categories"):
        db.execute("""CREATE TABLE IF NOT EXISTS group_categories (
            group_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY (group_id, category_id),
            FOREIGN KEY(group_id) REFERENCES operator_groups(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
        );""")

    # Webhooks
    if not _table_exists(db, "webhooks"):
        db.execute("""CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            url TEXT NOT NULL,
            eventos TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            secret TEXT,
            criado_em TEXT NOT NULL
        );""")

    # Chamados recorrentes
    if not _table_exists(db, "recurring_tickets"):
        db.execute("""CREATE TABLE IF NOT EXISTS recurring_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            frequencia TEXT NOT NULL DEFAULT 'mensal',
            dia_execucao INTEGER,
            hora_execucao TEXT NOT NULL DEFAULT '08:00',
            ticket_data TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            ultima_execucao TEXT,
            criado_em TEXT NOT NULL
        );""")

    # Base de conhecimento
    if not _table_exists(db, "kb_articles"):
        db.execute("""CREATE TABLE IF NOT EXISTS kb_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            categoria_id INTEGER,
            tags TEXT,
            autor_id INTEGER,
            autor_nome TEXT,
            publico INTEGER NOT NULL DEFAULT 1,
            visualizacoes INTEGER NOT NULL DEFAULT 0,
            ticket_id INTEGER,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            FOREIGN KEY(categoria_id) REFERENCES categories(id),
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE SET NULL
        );""")

    # Portal externo via token
    if not _table_exists(db, "portal_tokens"):
        db.execute("""CREATE TABLE IF NOT EXISTS portal_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            ticket_id INTEGER NOT NULL,
            email TEXT,
            criado_em TEXT NOT NULL,
            expira_em TEXT,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        );""")

    # Estoque (consumiveis)
    if not _table_exists(db, "stock_produtos"):
        db.execute("""CREATE TABLE IF NOT EXISTS stock_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'GERAL',
            descricao TEXT,
            unidade TEXT NOT NULL DEFAULT 'unidade',
            localizacao TEXT,
            quantidade_atual INTEGER NOT NULL DEFAULT 0,
            quantidade_minima INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );""")

    if not _table_exists(db, "stock_movimentacoes"):
        db.execute("""CREATE TABLE IF NOT EXISTS stock_movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            motivo TEXT,
            ticket_id INTEGER,
            usuario TEXT,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(produto_id) REFERENCES stock_produtos(id),
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE SET NULL
        );""")


    # Entradas por NF (lote de ativos + consumíveis)
    if not _table_exists(db, "entradas_nf"):
        db.execute("""CREATE TABLE IF NOT EXISTS entradas_nf (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_nf TEXT NOT NULL,
            numero_oc TEXT,
            fornecedor TEXT,
            base_destino TEXT,
            observacoes TEXT,
            usuario TEXT,
            status TEXT NOT NULL DEFAULT 'RASCUNHO',
            criado_em TEXT NOT NULL,
            confirmado_em TEXT
        );""")


    # IA assistida
    if not _table_exists(db, "ai_jobs"):
        db.execute("""CREATE TABLE IF NOT EXISTS ai_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            payload TEXT,
            result_text TEXT,
            error_message TEXT,
            created_em TEXT NOT NULL,
            updated_em TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        );""")

    if not _table_exists(db, "ticket_ai_insights"):
        db.execute("""CREATE TABLE IF NOT EXISTS ticket_ai_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            insight_type TEXT NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            created_em TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        );""")

    if not _table_exists(db, "entradas_nf_itens"):
        db.execute("""CREATE TABLE IF NOT EXISTS entradas_nf_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entrada_id INTEGER NOT NULL,
            tipo_item TEXT NOT NULL,
            tipo TEXT,
            modelo TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 1,
            prefixo_tag TEXT,
            serial_numbers TEXT,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            FOREIGN KEY(entrada_id) REFERENCES entradas_nf(id) ON DELETE CASCADE
        );""")

    if not _table_exists(db, "entradas_nf_assets"):
        db.execute("""CREATE TABLE IF NOT EXISTS entradas_nf_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entrada_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            asset_id INTEGER,
            stock_produto_id INTEGER,
            tag TEXT,
            serial_number TEXT,
            FOREIGN KEY(entrada_id) REFERENCES entradas_nf(id),
            FOREIGN KEY(asset_id) REFERENCES assets(id),
            FOREIGN KEY(item_id) REFERENCES entradas_nf_itens(id)
        );""")

    # Catálogo de produtos (referência para NFs)
    if not _table_exists(db, "catalogo_produtos"):
        db.execute("""CREATE TABLE IF NOT EXISTS catalogo_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo_oracle TEXT,
            tipo_item TEXT NOT NULL,
            valor_unitario REAL,
            prefixo_tag TEXT,
            unidade TEXT NOT NULL DEFAULT 'unidade',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );""")

    # Migrações leves de entradas por NF
    if _table_exists(db, "entradas_nf"):
        existing_nf_cols = {r[1] for r in db.execute("PRAGMA table_info(entradas_nf)").fetchall()}
        if "cancelado_em" not in existing_nf_cols:
            db.execute("ALTER TABLE entradas_nf ADD COLUMN cancelado_em TEXT")
        if "expira_em" not in existing_nf_cols:
            db.execute("ALTER TABLE entradas_nf ADD COLUMN expira_em TEXT")

    db.commit()

def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()
    migrate_db()

def init_app(app):
    app.teardown_appcontext(close_db)
