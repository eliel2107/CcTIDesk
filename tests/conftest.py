"""
conftest.py — configuração global dos testes.
Mocka o APScheduler para não iniciar jobs em background durante os testes.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True, scope="session")
def mock_scheduler():
    """Impede que o APScheduler inicie jobs reais durante os testes."""
    mock = MagicMock()
    mock.return_value = mock
    with patch("app.__init__._init_scheduler", return_value=None):
        yield
