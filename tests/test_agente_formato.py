from datetime import date
from decimal import Decimal

import pytest

from agil.agente import formato


@pytest.mark.parametrize(
    ("monto", "esperado"),
    [
        (Decimal("427.89"), "$427.89"),
        (Decimal("1234567.5"), "$1,234,567.50"),
        (Decimal("0"), "$0.00"),
        (Decimal("10.005"), "$10.00"),  # redondeo bancario de Decimal
    ],
)
def test_dinero(monto, esperado):
    assert formato.dinero(monto) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (Decimal("10.00"), "10%"),
        (Decimal("20"), "20%"),
        (Decimal("12.50"), "12.5%"),
        (Decimal("100"), "100%"),  # normalize() daría 1E+2 sin el formato :f
    ],
)
def test_porcentaje(valor, esperado):
    assert formato.porcentaje(valor) == esperado


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (date(2026, 11, 6), "viernes 6 de noviembre"),
        (date(2026, 11, 8), "domingo 8 de noviembre"),
        (date(2026, 1, 1), "jueves 1 de enero"),
        (date(2026, 12, 30), "miércoles 30 de diciembre"),
    ],
)
def test_fecha_en_espanol(dia, esperado):
    assert formato.fecha(dia) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("2025-11", "noviembre de 2025"),
        ("2026-01", "enero de 2026"),
        ("2026-12", "diciembre de 2026"),
    ],
)
def test_periodo_en_espanol(valor, esperado):
    assert formato.periodo(valor) == esperado
