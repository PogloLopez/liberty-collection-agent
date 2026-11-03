"""Horario permitido de contacto (marco_regulatorio): L-V 8:00-18:00, sáb 8:00-15:00, sin domingos
ni feriados. También interpreta el día que dice el cliente."""

import re
from datetime import date, datetime, time, timedelta, timezone

from agil.dominio.harness.texto import sin_tildes

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
_MESES = (
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
)
_RELATIVOS = {"hoy": 0, "manana": 1, "pasado manana": 2}
_NUMEROS = {
    "un": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "quince": 15,
}
_EN_DIAS = re.compile(r"(?:dentro de|en) (\d{1,2}|[a-z]+) dias?")
_DIA_MES = re.compile(r"(?:dia )?(\d{1,2})(?: de ([a-z]+))?")


def _dia_del_mes(dia: int, mes: str | None, hoy: date) -> date | None:
    """Día del mes: "el 15" es el próximo 15 (este mes o el siguiente); "15 de noviembre", el
    próximo que no haya pasado."""
    if mes is not None and mes not in _MESES:
        return None
    for salto in range(13):
        m = (hoy.month - 1 + salto) % 12 + 1
        anio = hoy.year + (hoy.month - 1 + salto) // 12
        if mes is not None and _MESES[m - 1] != mes:
            continue
        try:
            fecha = date(anio, m, dia)
        except ValueError:  # "el 31" en un mes de 30 días: el siguiente que lo tenga
            continue
        if fecha > hoy:
            return fecha
    return None


def resolver_dia(texto: str, hoy: date) -> date | None:
    """La fecha que dijo el cliente, contada desde `hoy` (D32): AAAA-MM-DD, "hoy", "mañana",
    "pasado mañana", un día de la semana (el próximo; "el viernes" dicho un viernes es en 7 días),
    "dentro de N días" o un día del mes ("el 15", "15 de noviembre"; el próximo que no haya pasado).
    None si no se entiende: "la próxima semana" o fechas relativas a la factura se piden concretas.
    """
    limpio = " ".join(sin_tildes(texto).lower().strip(" .,;:!?¿¡").split())
    for prefijo in ("el ", "este ", "proximo "):
        limpio = limpio.removeprefix(prefijo)
    limpio = limpio.removesuffix(" que viene")
    try:
        return date.fromisoformat(limpio)
    except ValueError:
        pass
    if limpio in _RELATIVOS:
        return hoy + timedelta(days=_RELATIVOS[limpio])
    if limpio in _DIAS:
        return hoy + timedelta(days=(_DIAS.index(limpio) - hoy.weekday()) % 7 or 7)
    if m := _EN_DIAS.fullmatch(limpio):
        n = int(m[1]) if m[1].isdigit() else _NUMEROS.get(m[1])
        return hoy + timedelta(days=n) if n else None
    if m := _DIA_MES.fullmatch(limpio):
        return _dia_del_mes(int(m[1]), m[2], hoy)
    return None
