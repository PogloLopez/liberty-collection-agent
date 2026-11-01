"""Horario permitido de contacto (marco_regulatorio): L-V 8:00-18:00, sáb 8:00-15:00, sin domingos
ni feriados. También interpreta el día que dice el cliente."""

import unicodedata
from datetime import date, datetime, time, timedelta, timezone

# Panamá no tiene horario de verano: el offset fijo evita depender de tzdata (falta en Windows).
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


_DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
_RELATIVOS = {"hoy": 0, "manana": 1, "pasado manana": 2}


def resolver_dia(texto: str, hoy: date) -> date | None:
    """La fecha que dijo el cliente: AAAA-MM-DD, "hoy", "mañana", "pasado mañana" o un día de la
    semana (el próximo; "el viernes" dicho un viernes es en 7 días). None si no se entiende (D32).
    """
    limpio = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = " ".join(limpio.lower().strip(" .,;:!?¿¡").split())
    for prefijo in ("el ", "este ", "proximo "):
        limpio = limpio.removeprefix(prefijo)
    try:
        return date.fromisoformat(limpio)
    except ValueError:
        pass
    if limpio in _RELATIVOS:
        return hoy + timedelta(days=_RELATIVOS[limpio])
    if limpio in _DIAS:
        return hoy + timedelta(days=(_DIAS.index(limpio) - hoy.weekday()) % 7 or 7)
    return None
