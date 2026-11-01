"""Cómo se ven las cifras al renderizar los placeholders (B4). Solo el código las escribe."""

from datetime import date
from decimal import Decimal

_MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def dinero(monto: Decimal) -> str:
    return f"${monto:,.2f}"


def porcentaje(valor: Decimal) -> str:
    return f"{valor.normalize():f}%"


def fecha(dia: date) -> str:
    """'viernes 6 de noviembre'."""
    return f"{_DIAS[dia.weekday()]} {dia.day} de {_MESES[dia.month - 1]}"


def periodo(valor: str) -> str:
    """'2025-11' → 'noviembre de 2025'."""
    anio, mes = valor.split("-")
    return f"{_MESES[int(mes) - 1]} de {anio}"
