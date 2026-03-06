"""
Instâncias das extensões Flask criadas aqui para evitar circular import.
Inicializadas com a app em create_app() via .init_app(app).
"""
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["300 per hour"])
