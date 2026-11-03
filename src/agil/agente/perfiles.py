"""Perfil por segmento (D2, D33): un runtime, N configuraciones. Los textos viven en `prompts/` para
que cartera y legal los revisen sin tocar código (P1)."""

import json
from datetime import datetime

from pydantic import BaseModel

from agil.agente import formato
from agil.dominio.modelos import Cliente, Segmento
from agil.dominio.repositorio.memoria import RAIZ

PROMPTS = RAIZ / "prompts"


class Perfil(BaseModel):
    segmento: Segmento
    max_turnos: int
    max_caracteres: int
    prompt: str  # base de marca + ajuste del segmento


def cargar_perfil(segmento: Segmento) -> Perfil:
    config = json.loads((PROMPTS / "perfiles.json").read_text(encoding="utf-8"))
    base = (PROMPTS / "base.md").read_text(encoding="utf-8")
    ajuste = (PROMPTS / "segmentos" / f"{segmento.value}.md").read_text(encoding="utf-8")
    return Perfil(
        segmento=segmento,
        max_caracteres=config["max_caracteres"],
        prompt=f"{base}\n\n{ajuste}",
        **config["segmentos"][segmento.value],
    )


def prompt_sistema(perfil: Perfil, cliente: Cliente, ahora: datetime) -> str:
    """Sin datos de la cuenta: esos llegan por tools, después de verificar la cédula (D5). Sin la
    hora: cambia cada minuto y rompería el caché por prefijo; va en el `[contexto]` (D47)."""
    hoy = ahora.date()
    return (
        f"{perfil.prompt}\n\n## Esta conversación\n"
        f"- Cliente: {cliente.nombre.split()[0]}.\n"
        f"- Hoy es {formato.fecha(hoy)} de {hoy.year}.\n"
        f"- Máximo {perfil.max_caracteres} caracteres por mensaje."
    )


def linea_hora(ahora: datetime) -> str:
    """La hora y el saludo que toca, para el bloque `[contexto]` del final del mensaje."""
    saludo = (
        "buenos días"
        if ahora.hour < 12
        else "buenas tardes"
        if ahora.hour < 19
        else "buenas noches"
    )
    return f'[contexto] Son las {ahora:%H:%M}: si saludas, "{saludo}".'
