"""Validador de salida, antes de renderizar (harness_del_agente, D4)."""

import re
import unicodedata

from agil.dominio.modelos import Validacion
from agil.dominio.placeholders import PATRON, placeholders_en

_PERMITIDO = re.compile(r"\bcuatro digitos\b|\bmil (?:gracias|disculpas)\b", re.IGNORECASE)

_NUMEROS = (
    r"cero|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince"
    r"|dieci\w+|veinte|veinti\w+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa"
    r"|cien|ciento|\w*cientos|\w*cientas|quinientos|quinientas|mil|miles|millon|millones"
)
_MESES = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre"
    r"|noviembre|diciembre"
)
_DIAS = r"lunes|martes|miercoles|jueves|viernes|sabado|domingo"
_MONEDA = r"dolar|dolares|balboas|usd|centavos?"  # "balboa" solo es también Avenida Balboa
_HORAS = r"la una|mediodia|medianoche|el primero del?|dia primero"

_REGLAS = [
    (
        re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|net|org|pa|io|ly|co|app)\b", re.I),
        "una URL literal",
    ),
    # Dominio genérico solo en minúsculas, para no confundir "Gracias.Hoy" con una URL.
    (re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b"), "una URL literal"),
    (re.compile(r"%|\bpor ?ciento\b", re.I), "un porcentaje"),
    (re.compile(rf"\$|\bB/\.|\b(?:{_MONEDA})\b", re.I), "un monto o moneda"),
    (re.compile(r"\d+"), "una cifra"),
    (re.compile(rf"\b(?:{_MESES})\b", re.I), "un mes"),
    (re.compile(rf"\b(?:{_DIAS})\b", re.I), "un día de la semana"),
    (re.compile(rf"\b(?:{_HORAS})\b", re.I), "una hora o fecha"),
    (re.compile(rf"\b(?:{_NUMEROS})\b", re.I), "un número en palabras"),
]


def _sin_tildes(texto: str) -> str:
    """Quita tildes para que "millón", "millon" y su forma NFD coincidan con las listas."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def validar_salida(
    texto: str, placeholders_permitidos: set[str], max_caracteres: int
) -> Validacion:
    """Bloquea cifras, %, montos, fechas, horas, meses o números en palabras fuera de placeholders
    (salvo "cuatro dígitos"), placeholders desconocidos, URLs literales y textos largos."""
    if len(texto) > max_caracteres:
        return Validacion(
            ok=False, motivo=f"Mensaje demasiado largo: máximo {max_caracteres} caracteres."
        )
    desconocidos = placeholders_en(texto) - placeholders_permitidos
    if desconocidos:
        nombres = ", ".join(f"{{{{{p}}}}}" for p in sorted(desconocidos))
        return Validacion(ok=False, motivo=f"Placeholder no disponible: {nombres}. No lo uses.")
    normalizado = re.sub(r"\s+", " ", _sin_tildes(PATRON.sub(" ", texto)))
    resto = _PERMITIDO.sub(" ", normalizado)
    if "{" in resto or "}" in resto:
        return Validacion(ok=False, motivo="Placeholder mal formado: usa {{nombre}}.")
    for patron, que in _REGLAS:
        if m := patron.search(resto):
            return Validacion(
                ok=False,
                motivo=f"Escribiste {que} ('{m.group(0)}'): usa un placeholder del contexto.",
            )
    return Validacion(ok=True)
