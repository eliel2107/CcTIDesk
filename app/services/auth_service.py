from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from app.db import get_db

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def create_user(nome: str, email: str, password: str, role: str = "admin", active: bool = True):
    db = get_db()
    db.execute(
        "INSERT INTO users (nome, email, password_hash, role, active, created_em) VALUES (?, ?, ?, ?, ?, ?)",
        (nome.strip(), email.strip().lower(), generate_password_hash(password), role, 1 if active else 0, now())
    )
    db.commit()

def get_user_by_email(email: str):
    return get_db().execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()

def get_user(user_id: int):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def authenticate(email: str, password: str):
    user = get_user_by_email(email)
    return user if user and check_password_hash(user["password_hash"], password) else None

def ensure_default_admin():
    email = current_app.config["ADMIN_DEFAULT_EMAIL"]
    if not get_user_by_email(email):
        create_user("Administrador", email, current_app.config["ADMIN_DEFAULT_PASSWORD"], "admin", True)
