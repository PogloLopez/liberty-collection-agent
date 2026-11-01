"""Llamadas laterales a modelos pequeños, fuera del bucle del agente: estratega (D16), moderación
(D35) y resumen al cierre (D34). Si fallan, la conversación sigue: nunca bloquean al cliente."""

import json
import logging
import re
from enum import StrEnum
from functools import cache

from pydantic import BaseModel
from strands import Agent
from strands.models import Model

from agil.agente.perfiles import PROMPTS
from agil.dominio.harness.texto import sin_tildes
from agil.dominio.modelos import FlagMemoria

log = logging.getLogger(__name__)


class Momento(StrEnum):
    """Catálogo cerrado del estratega; cada momento tiene su tarjeta en prompts/estrategias.json."""

    duda = "duda"
    listo_para_pagar = "listo_para_pagar"
    pago_reciente = "pago_reciente"
    objecion_monto = "objecion_monto"
    dificultad_economica = "dificultad_economica"
    pide_mas_descuento = "pide_mas_descuento"
    promesa_vaga = "promesa_vaga"
    evasion = "evasion"
    enojo = "enojo"
    disputa = "disputa"
    pide_humano = "pide_humano"
    otro = "otro"


class Resumen(BaseModel):
    texto: str
    flags: list[FlagMemoria]


@cache
def _prompt(nombre: str) -> str:
    return (PROMPTS / nombre).read_text(encoding="utf-8")


@cache
def tarjetas() -> dict[str, str]:
    return json.loads(_prompt("estrategias.json"))


def preguntar(modelo: Model, sistema: str, texto: str) -> str:
    agente = Agent(model=modelo, system_prompt=sistema, callback_handler=None)
    return str(agente(texto)).strip()


def _transcripcion(lineas: list[tuple[str, str]]) -> str:
    """Las líneas ya llegan enmascaradas desde el orquestador (D24)."""
    return "\n".join(f"{rol}: {texto}" for rol, texto in lineas)


def clasificar_momento(modelo: Model, lineas: list[tuple[str, str]]) -> Momento | None:
    try:
        salida = preguntar(modelo, _prompt("estratega.md"), _transcripcion(lineas[-6:]))
    except Exception:
        log.exception("Estratega no disponible")
        return None
    limpio = sin_tildes(salida.lower())
    return next((m for m in Momento if re.search(rf"\b{m.value}\b", limpio)), None)


def tarjeta_estrategia(momento: Momento) -> str | None:
    return tarjetas().get(momento.value)


def es_abusivo(modelo: Model, mensaje: str) -> bool:
    try:
        salida = preguntar(modelo, _prompt("moderacion.md"), mensaje)
    except Exception:
        log.exception("Moderación no disponible: el mensaje pasa")
        return False
    return salida.startswith("1")


def resumir(modelo: Model, lineas: list[tuple[str, str]]) -> Resumen | None:
    try:
        salida = preguntar(modelo, _prompt("resumen.md"), _transcripcion(lineas))
        crudo = json.loads(salida[salida.index("{") : salida.rindex("}") + 1])
        flags = [f for f in crudo.get("flags", []) if f in FlagMemoria.__members__]
        return Resumen(texto=crudo["texto"], flags=list(dict.fromkeys(flags)))
    except Exception:
        log.exception("Resumen no disponible o inválido")
        return None
