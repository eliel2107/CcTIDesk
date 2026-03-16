"""
Pacote de rotas — Blueprint "routes" dividido em módulos temáticos.
Todos os sub-módulos usam o mesmo blueprint para manter url_for("routes.xxx") funcionando.
"""

from flask import Blueprint

bp = Blueprint("routes", __name__)

# Importar sub-módulos que registram rotas no bp
from app.routes import (  # noqa: F401
    dashboard,
    tickets,
    queue,
    workflow,
    comments,
    approval,
    search,
    logs,
    groups,
    webhooks,
    recurring,
    api_routes,
)
