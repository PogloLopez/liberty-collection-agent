"""Horario permitido de contacto (marco_regulatorio): L-V 8:00-18:00, sáb 8:00-15:00, sin domingos
ni feriados."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    ZONA = ZoneInfo("America/Panama")
except ZoneInfoNotFoundError:
    # Windows sin tzdata. Panamá no tiene horario de verano: el offset fijo es equivalente.
    ZONA = timezone(timedelta(hours=-5), "America/Panama")

# Art. 46 del Código de Trabajo + 20-dic (duelo nacional). El 2-nov no se contacta (datos_mock.md);
# el 4-nov es hábil.
_FIJOS = [
    (1, 1),
    (1, 9),
    (5, 1),
    (11, 2),
    (11, 3),
    (11, 5),
    (11, 10),
    (11, 28),
    (12, 8),
    (12, 20),
    (12, 25),
]
_MOVILES = {
    2025: [date(2025, 3, 3), date(2025, 3, 4), date(2025, 4, 18)],
    2026: [date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3)],
}

_INICIO = time(8, 0)
_FIN_SEMANA = time(18, 0)
_FIN_SABADO = time(15, 0)


def _feriados(anio: int) -> set[date]:
    if anio not in _MOVILES:
        raise ValueError(f"sin calendario de feriados para {anio}")
    dias = {date(anio, m, d) for m, d in _FIJOS} | set(_MOVILES[anio])
    # Si el feriado cae en domingo se descansa el lunes siguiente (art. 47).
    return dias | {d + timedelta(days=1) for d in dias if d.weekday() == 6}


def es_feriado(dia: date) -> bool:
    """Día sin contacto: feriados nacionales, 20-dic, 2-nov y el lunes de un feriado en domingo."""
    return dia in _feriados(dia.year)


def en_horario_permitido(momento: datetime) -> bool:
    """`momento` con zona horaria; se evalúa en America/Panama. 18:00 y 15:00 ya quedan fuera."""
    if momento.tzinfo is None:
        raise ValueError("momento debe tener zona horaria")
    local = momento.astimezone(ZONA)
    dia, hora = local.date(), local.time()
    if dia.weekday() == 6 or es_feriado(dia):
        return False
    fin = _FIN_SABADO if dia.weekday() == 5 else _FIN_SEMANA
    return _INICIO <= hora < fin
