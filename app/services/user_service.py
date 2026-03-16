from datetime import datetime
from werkzeug.security import generate_password_hash
from app.db import get_db

ROLES = ["admin", "operador", "solicitante", "viewer"]

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def list_users():
    return get_db().execute(
        "SELECT id, nome, email, role, active, created_em FROM users ORDER BY nome ASC"
    ).fetchall()

def get_user_by_id(user_id: int):
    return get_db().execute(
        "SELECT id, nome, email, role, active, created_em FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

def create_user(nome: str, email: str, password: str, role: str = "operador", active: bool = True):
    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    role = (role or "operador").strip().lower()

    if not nome:
        raise ValueError("Nome é obrigatório.")
    if not email:
        raise ValueError("E-mail é obrigatório.")
    if len(password) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    if role not in ROLES:
        raise ValueError(f"Perfil inválido. Use: {', '.join(ROLES)}")

    db = get_db()
    cur = db.execute(
        "INSERT INTO users (nome, email, password_hash, role, active, created_em) VALUES (?, ?, ?, ?, ?, ?)",
        (nome, email, generate_password_hash(password), role, 1 if active else 0, now()),
    )
    db.commit()
    return cur.lastrowid

def update_user(user_id: int, nome: str, email: str, role: str, active: bool):
    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    role = (role or "operador").strip().lower()

    if not nome:
        raise ValueError("Nome é obrigatório.")
    if not email:
        raise ValueError("E-mail é obrigatório.")
    if role not in ROLES:
        raise ValueError(f"Perfil inválido. Use: {', '.join(ROLES)}")

    db = get_db()
    db.execute(
        "UPDATE users SET nome=?, email=?, role=?, active=? WHERE id=?",
        (nome, email, role, 1 if active else 0, user_id),
    )
    db.commit()

def set_user_active(user_id: int, active: bool):
    db = get_db()
    db.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, user_id))
    db.commit()

def delete_user(user_id: int, current_user_id: int):
    """Remove um usuário do sistema.
    Proteções:
    - Não permite apagar o próprio usuário logado.
    - Não permite apagar se for o último admin ativo do sistema.
    """
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise ValueError("Usuário não encontrado.")
    if user_id == current_user_id:
        raise ValueError("Você não pode apagar o seu próprio usuário.")
    if row["role"] == "admin":
        admin_count = db.execute(
            "SELECT COUNT(*) as c FROM users WHERE role='admin' AND active=1"
        ).fetchone()["c"]
        if admin_count <= 1:
            raise ValueError("Não é possível apagar o último administrador ativo do sistema.")
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
