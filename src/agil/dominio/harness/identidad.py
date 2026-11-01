"""Verificación por los últimos 4 dígitos de la cédula (D5, D24). El número nunca llega al LLM.

Formatos completos reconocidos: numérico (8-765-1043) y con prefijo (PE-3-1234, E-8-142908); de un
RUC se aceptan solo los 4 dígitos sueltos. Una fecha D-MM-AAAA no cuenta como cédula.
Solo ASCII: un dígito Unicode ("２９０８") no es un intento válido.
"""

import hmac
import re

from agil.dominio.modelos import Cliente

# Provincia 1-13 para no confundir una fecha DD-MM-AAAA con una cédula.
_CEDULA = re.compile(
    r"(?<![\w-])(?:[A-Za-z]{1,2}-(?:1[0-3]|[1-9])|(?:1[0-3]|[1-9])-[0-9]{1,4})-[0-9]{1,6}(?![\w-])",
    re.ASCII,
)
_FECHA = re.compile(r"[0-9]{1,2}-(?:0?[1-9]|1[0-2])-(?:19|20)[0-9]{2}", re.ASCII)
# Dígitos sueltos separados solo por espacios ("2 9 0 8"); punto y guion son montos o fechas.
_GRUPO = re.compile(r"[0-9](?: ?[0-9])*", re.ASCII)


def ultimos_cuatro(cedula: str) -> str:
    """Sin letras ni guiones: 6-712-982 → 2982, E-8-142908 → 2908."""
    return re.sub(r"[^0-9]", "", cedula)[-4:]


def extraer_digitos(mensaje: str) -> str | None:
    """Los 4 dígitos si el mensaje es un intento de verificación; None si no.

    "1500" es ambiguo: el router solo la usa mientras espera la verificación.
    """
    cedulas = [c for c in _CEDULA.findall(mensaje) if not _FECHA.fullmatch(c)]
    if len(cedulas) == 1:
        return ultimos_cuatro(cedulas[0])
    grupos = [g.replace(" ", "") for g in _GRUPO.findall(mensaje)]
    if len(grupos) == 1 and len(grupos[0]) == 4:
        return grupos[0]
    return None


def enmascarar(texto: str, solo_cedula: bool) -> str:
    """Tapa las cédulas completas y, si `solo_cedula` es False (sin verificar), cualquier dígito.

    Corre antes de cualquier modelo (D24), aparte de `extraer_digitos`: un mensaje con dos números
    no es un intento de verificación, pero igual se enmascara.
    """
    texto = _CEDULA.sub(lambda m: re.sub(r"[0-9]", "•", m.group(0)), texto)
    return texto if solo_cedula else re.sub(r"[0-9]", "•", texto)


def verificar(cliente: Cliente, digitos: str) -> bool:
    if not re.fullmatch(r"[0-9]{4}", digitos):
        return False
    return hmac.compare_digest(ultimos_cuatro(cliente.cedula), digitos)
