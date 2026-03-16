"""
Funções utilitárias compartilhadas por todos os serviços.
Sem dependência de Flask — apenas Python puro + datetime.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_ymd() -> str:
    return date.today().strftime("%Y-%m-%d")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def _clean(s: Optional[str]) -> str:
    return (s or "").strip()


def _escape_like(s: str) -> str:
    """Escapa caracteres especiais do LIKE para evitar falsos positivos."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_param(s: str) -> str:
    """Retorna parâmetro LIKE com escape seguro: %valor%"""
    return f"%{_escape_like(s)}%"


def _parse_float(s: Optional[str]) -> Optional[float]:
    s = _clean(s)
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError("Valor estimado inválido. Use número (ex: 1500.00).")


def _validate_date_ymd(s: Optional[str]) -> Optional[str]:
    s = _clean(s)
    if not s:
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        raise ValueError("Data limite inválida. Use YYYY-MM-DD (ex: 2026-03-15).")


def validate_choice(value: str, allowed: List[str], field: str):
    if value is None:
        raise ValueError(f"{field} é obrigatório.")
    v = value.strip().upper()
    if v not in allowed:
        raise ValueError(f"{field} inválido: '{value}'. Use: {allowed}")
    return v


def _days_between(date_ymd: str, today_ymd: str) -> int:
    d1 = datetime.strptime(date_ymd, "%Y-%m-%d").date()
    d2 = datetime.strptime(today_ymd, "%Y-%m-%d").date()
    return (d2 - d1).days
