"""Horario permitido y feriados de Panamá; el historial de contactos debe respetarlos."""

import json
from collections import Counter
from datetime import UTC, date, datetime

import pytest

from agil.dominio.calendario import ZONA, en_horario_permitido, es_feriado
from agil.dominio.repositorio.memoria import DATOS_MOCK

CONTACTOS = json.loads((DATOS_MOCK / "historial_contactos.json").read_text(encoding="utf-8"))


def _pa(*args: int) -> datetime:
    return datetime(*args, tzinfo=ZONA)


@pytest.mark.parametrize(
    "dia",
    [
        date(2025, 12, 20),
        date(2026, 12, 20),
        date(2026, 11, 2),
        date(2026, 11, 3),
        date(2026, 11, 5),
        date(2026, 1, 9),
        date(2026, 2, 17),
        date(2026, 4, 3),
        date(2025, 12, 25),
    ],
)
def test_feriados(dia):
    assert es_feriado(dia)


@pytest.mark.parametrize("dia", [date(2026, 11, 4), date(2026, 11, 6), date(2026, 2, 18)])
def test_dias_habiles(dia):
    assert not es_feriado(dia)


def test_feriado_en_domingo_se_traslada_al_lunes():
    assert es_feriado(date(2026, 12, 21))


@pytest.mark.parametrize(
    ("momento", "permitido"),
    [
        (_pa(2026, 11, 6, 8, 0), True),
        (_pa(2026, 11, 6, 7, 59), False),
        (_pa(2026, 11, 6, 17, 59), True),
        (_pa(2026, 11, 6, 18, 0), False),
        (_pa(2026, 11, 7, 14, 59), True),
        (_pa(2026, 11, 7, 15, 0), False),
        (_pa(2026, 11, 8, 10, 0), False),
        (_pa(2026, 11, 3, 10, 0), False),
        (_pa(2026, 11, 4, 10, 0), True),
        (datetime(2026, 11, 6, 13, 0, tzinfo=UTC), True),
        (datetime(2026, 11, 6, 23, 0, tzinfo=UTC), False),
    ],
)
def test_en_horario_permitido(momento, permitido):
    assert en_horario_permitido(momento) is permitido


def test_momento_sin_zona_falla():
    with pytest.raises(ValueError):
        en_horario_permitido(datetime(2026, 11, 6, 10, 0))


@pytest.mark.parametrize("contacto", CONTACTOS, ids=lambda c: c["contacto_id"])
def test_historial_en_horario_permitido(contacto):
    assert en_horario_permitido(datetime.fromisoformat(contacto["fecha"]))


def test_historial_maximo_un_contacto_por_cliente_y_dia():
    por_dia = Counter(
        (c["customer_id"], datetime.fromisoformat(c["fecha"]).astimezone(ZONA).date())
        for c in CONTACTOS
    )
    assert max(por_dia.values()) == 1


def test_anio_sin_calendario_falla():
    with pytest.raises(ValueError):
        es_feriado(date(2027, 1, 1))
