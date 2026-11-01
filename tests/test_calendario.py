"""Horario permitido y feriados de Panamá; el historial de contactos debe respetarlos."""

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import pytest

from agil.dominio.reglas.calendario import ZONA, en_horario_permitido, es_feriado, resolver_dia
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


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("el miércoles", date(2026, 11, 11)),
        ("Mañana", date(2026, 11, 7)),
        ("pasado mañana", date(2026, 11, 8)),
        ("hoy", date(2026, 11, 6)),
        ("viernes", date(2026, 11, 13)),  # dicho un viernes: el de la otra semana
        ("EL  SÁBADO", date(2026, 11, 7)),
        ("2026-11-09", date(2026, 11, 9)),
        ("el 15", date(2026, 11, 15)),
        ("cuando pueda", None),
        ("el próximo martes.", date(2026, 11, 10)),
        ("este lunes?", date(2026, 11, 9)),
        ("", None),
    ],
)
def test_resolver_dia(texto, esperado):
    assert resolver_dia(texto, date(2026, 11, 6)) == esperado


_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@pytest.mark.parametrize("hoy", [date(2026, 11, 2) + timedelta(days=i) for i in range(7)])
@pytest.mark.parametrize("nombre", _SEMANA)
def test_resolver_dia_de_la_semana_es_el_proximo(nombre, hoy):
    dia = resolver_dia(nombre, hoy)
    assert dia.weekday() == _SEMANA.index(nombre)
    assert 1 <= (dia - hoy).days <= 7


@pytest.mark.parametrize(
    ("texto", "hoy", "esperado"),
    [
        ("mañana", date(2026, 12, 31), date(2027, 1, 1)),
        ("pasado mañana", date(2026, 12, 31), date(2027, 1, 2)),
        ("el lunes", date(2026, 12, 31), date(2027, 1, 4)),
        ("jueves", date(2026, 12, 31), date(2027, 1, 7)),
        ("mañana", date(2028, 2, 28), date(2028, 2, 29)),
        ("el 5", date(2026, 12, 20), date(2027, 1, 5)),
    ],
)
def test_resolver_dia_cruza_mes_y_anio(texto, hoy, esperado):
    assert resolver_dia(texto, hoy) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("2026-02-30", None),
        ("2026-13-01", None),
        ("...", None),
        ("¿?!", None),
        ("   ", None),
        ("el", None),
        ("proximo jueves", date(2026, 11, 12)),
        ("  Pasado   Manana!!", date(2026, 11, 8)),
        ("¡el viernes!", date(2026, 11, 13)),
        ("MIERCOLES,", date(2026, 11, 11)),
        (" 2026-11-09. ", date(2026, 11, 9)),
        ("lunes o martes", None),
    ],
)
def test_resolver_dia_bordes(texto, esperado):
    assert resolver_dia(texto, date(2026, 11, 6)) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("dentro de 10 días", date(2026, 11, 16)),
        ("en 3 dias", date(2026, 11, 9)),
        ("en cinco días", date(2026, 11, 11)),
        ("dentro de un día", date(2026, 11, 7)),
        ("en 0 días", None),
        ("en muchos días", None),
        ("el 15 de noviembre", date(2026, 11, 15)),
        ("el día 20", date(2026, 11, 20)),
        ("el 6", date(2026, 12, 6)),  # hoy es 6: el del mes siguiente
        ("el 3 de noviembre", date(2027, 11, 3)),  # ya pasó este año
        ("el 31", date(2026, 12, 31)),  # noviembre no tiene 31
        ("31 de noviembre", None),
        ("el 15 de brumario", None),
        ("el lunes que viene", date(2026, 11, 9)),
        ("la próxima semana", None),
        ("10 días después de la fecha de pago", None),
    ],
)
def test_resolver_dia_plazos_y_dias_del_mes(texto, esperado):
    assert resolver_dia(texto, date(2026, 11, 6)) == esperado
