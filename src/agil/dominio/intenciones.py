"""Lo que la Lambda router resuelve sin LLM: no contactar explícito (D13) y botones (D22)."""

import re
import unicodedata
from enum import StrEnum


class Boton(StrEnum):
    confirmar = "btn_confirmar"
    cancelar = "btn_cancelar"


_EXPLICITAS = (
    r"stop|baja"
    r"|no (?:me|nos) (?:escriban|escribas|escriba|contacten|contactes|contacte|molesten"
    r"|manden (?:mas )?mensajes|envien (?:mas )?mensajes)"
    r"|no (?:me|nos) (?:vuelvan a (?:escribir|contactar)|sigan (?:escribiendo|contactando"
    r"|mandando mensajes))"
    r"|no quiero (?:que me (?:escriban|contacten|sigan (?:escribiendo|contactando"
    r"|mandando mensajes))|recibir (?:mas )?mensajes|mas mensajes)"
    r"|dejen de (?:escribirme|contactarme|molestarme|mandarme mensajes|enviarme mensajes)"
    r"|(?:borren|eliminen|saquen) mi numero"
)
_CORTESIA = r"por favor|porfa|gracias|ya|senores|les pido que|le pido que"
# Lista blanca de la oración entera: cualquier otra palabra antes o después ("hoy", "por
# whatsapp", "ya pague", "nunca dije que") la vuelve ambigua y la resuelve el agente.
_ORACION = re.compile(
    rf"^(?:(?:{_CORTESIA}) )*(?:{_EXPLICITAS})(?: (?:nunca(?: mas)?|mas))?"
    rf"(?: (?:{_CORTESIA}))*$"
)
_SOLO_CORTESIA = re.compile(rf"^(?:{_CORTESIA})(?: (?:{_CORTESIA}))*$")


def _normalizar(mensaje: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", mensaje.lower())
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", sin_tildes).split())


def pide_no_contacto(mensaje: str) -> bool:
    """Frases explícitas ("STOP", "no me escriban"...).

    Lista blanca del mensaje entero: cada oración es explícita o solo cortesía. Cualquier otra
    cosa ("No me escriban. Hasta el lunes", "¿no me escriban?") va al agente, que tiene
    `derivar_solicitud_contacto`: un falso negativo cuesta un turno; uno positivo pausa WhatsApp.
    """
    if "?" in mensaje or "¿" in mensaje:
        return False
    oraciones = [_normalizar(o) for o in re.split(r"[.!;\n]+", mensaje)]
    oraciones = [o for o in oraciones if o and not _SOLO_CORTESIA.match(o)]
    return bool(oraciones) and all(_ORACION.match(o) for o in oraciones)
