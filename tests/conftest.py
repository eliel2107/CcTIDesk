"""Configuração global de testes.

Objetivos:
- garantir que a raiz do projeto esteja no PYTHONPATH mesmo quando o pytest
  for executado a partir de um diretório diferente da raiz;
- impedir a inicialização do APScheduler durante os testes;
- manter os imports absolutos do projeto estáveis.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True, scope="session")
def mock_scheduler():
    """Impede que o APScheduler inicie jobs reais durante os testes.

    O patch é aplicado no símbolo real usado por ``create_app``.
    """
    app_module = importlib.import_module("app")
    with patch.object(app_module, "_init_scheduler", return_value=None):
        yield
