"""Lo que la Lambda router resuelve sin LLM: no contactar explícito (D13), botones (D22) y
mensajes sin sentido (D40)."""

import re
from enum import StrEnum

from agil.dominio.harness.texto import sin_tildes


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
    return " ".join(re.sub(r"[^\w\s]", " ", sin_tildes(mensaje.lower())).split())


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


# La persona va pegada al verbo: "quiero pagar en persona" o "lo que me dijo el asesor" no cuentan.
_PERSONA = r"(?:una? )?(?:asesora?|human[oa]|persona|operadora?|ejecutiv[oa]|agente)"
_CON = rf"(?:con (?:{_PERSONA}|alguien)|a {_PERSONA})"
_PIDE_HUMANO = re.compile(
    rf"\b(?:hablar|comunicarme|pasar(?:me)?|pasame|paseme|pasenme|atienda) {_CON}\b"
    rf"|\b(?:quiero|necesito|deme|denme) {_PERSONA}\b|^{_PERSONA}(?: por favor)?$"
)
_NEGADO = re.compile(rf"\bno (?:quiero|necesito) (?:hablar {_CON}|{_PERSONA})\b")


def pide_humano(mensaje: str) -> bool:
    """Pide hablar con un asesor ("quiero hablar con una persona", "un asesor por favor"). Dos
    pedidos lo pasan a un asesor (D45)."""
    m = _normalizar(mensaje)
    return bool(_PIDE_HUMANO.search(m)) and not _NEGADO.search(m)


# Palabras frecuentes: si aparece una, el mensaje tiene sentido aunque traiga ruido.
_COMUNES = frozenset(
    re.findall(
        r"\w+",
        "a ah al algo aqui asi bien bueno buenas buenos como con cual cuando cuanto de "
        "debo del dia dias el ella en entiendo es esa ese eso esta estoy favor gracias "
        "hola hoy la las le lo los luego mal mas me mi mucho muy nada no nos o ok okey "
        "para pero por porque pues puedo que quien quiero se si sin son su tengo un una "
        "uno vale y ya yo pago pagar factura cuenta "
        "saldo cuotas plazo link",
    )
)
_CONSONANTES = re.compile(r"[bcdfghjklmnpqrstvwxz]{4,}")
_GRUPOS_VALIDOS = re.compile(r"[nbrs]?(?:str|scr|spl|spr)")  # instrucción, obstrucción, transcribir


def sin_sentido(mensaje: str) -> bool:
    """Teclazos ("oipuhwegpub"): ninguna palabra frecuente y alguna palabra con cuatro consonantes
    distintas seguidas o de más de 25 letras. Sin LLM; un falso positivo cuesta un "¿me lo repite?".
    Falso positivo conocido: apellidos extranjeros como "Schwarz" (D40)."""
    sin_enlaces = re.sub(r"\S+[@/.]\S+", " ", sin_tildes(mensaje.lower()))  # links y correos
    # Letras repetidas cuentan una vez: "pfff", "mmmm" y "hmmm" son expresiones, no teclazos.
    palabras = [re.sub(r"(.)\1+", r"\1", p) for p in re.findall(r"[a-zñ]+", sin_enlaces)]
    if not palabras or any(p in _COMUNES for p in palabras):
        return False
    return any(_CONSONANTES.search(_GRUPOS_VALIDOS.sub("", p)) or len(p) > 25 for p in palabras)
