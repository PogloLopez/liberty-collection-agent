"""Campaña saliente de la demo (D20, D38): el botón "Que sean las 9 AM" hace en Python lo que en la
nube hará el flujo programado: filtro de contacto, segmento, plantilla del segmento y envío."""

import json
from datetime import date, datetime, time

from opentelemetry import trace
from pydantic import BaseModel, Field

from agil.agente.orquestador import Orquestador
from agil.agente.perfiles import PROMPTS
from agil.agente.sesion import Sesion
from agil.dominio.modelos import Contacto
from agil.dominio.reglas.calendario import ZONA
from agil.dominio.reglas.elegibilidad import puede_enviar_ahora
from agil.dominio.reglas.segmentacion import segmentar
from agil.dominio.repositorio.interfaz import Repositorio

CAMPANA_ID = "CP-DEMO"
_tracer = trace.get_tracer("agil.campana")


class Envio(BaseModel):
    sesion: Sesion | None = None  # None si el filtro no dejó enviar
    plantilla: str | None = None
    pasos: list[tuple[str, str]] = Field(default_factory=list)


def plantilla(segmento: str, nombre: str) -> tuple[str, str]:
    """Sin montos ni datos de la cuenta (D5): solo que hay un saldo pendiente."""
    p = json.loads((PROMPTS / "plantillas.json").read_text(encoding="utf-8"))[segmento]
    return p["id"], p["texto"].format(nombre=nombre.split()[0])


def que_sean_las_9(
    orq: Orquestador, customer_id: str, conversacion_id: str, hoy: date, modo_demo: bool = False
) -> Envio:
    """Un span por envío, sin el texto ni el nombre del cliente."""
    with _tracer.start_as_current_span("agil.campana") as span:
        envio = _enviar(orq, customer_id, conversacion_id, hoy, modo_demo)
        span.set_attribute("session.id", conversacion_id)
        span.set_attribute("agil.modo_demo", modo_demo)
        span.set_attribute("agil.enviado", envio.sesion is not None)
        return envio


def _enviar(
    orq: Orquestador, customer_id: str, conversacion_id: str, hoy: date, modo_demo: bool
) -> Envio:
    ok, pasos = filtrar(orq.repo, customer_id, hoy, modo_demo)
    return enviar(orq, customer_id, conversacion_id, hoy, pasos) if ok else Envio(pasos=pasos)


def filtrar(
    repo: Repositorio, customer_id: str, hoy: date, modo_demo: bool
) -> tuple[bool, list[tuple[str, str]]]:
    """Primer paso del flujo (en la nube, un estado de Step Functions): ¿se le puede escribir?"""
    momento = datetime.combine(hoy, time(9), ZONA)
    v = puede_enviar_ahora(repo, customer_id, momento, tope_diario=not modo_demo)
    filtro = v.motivo or ("aprobado (modo demo: sin tope diario)" if modo_demo else "aprobado")
    return v.ok, [("Disparador", "las 9 AM (simulado)"), ("Filtro de contacto", filtro)]


def enviar(
    orq: Orquestador,
    customer_id: str,
    conversacion_id: str,
    hoy: date,
    pasos: list[tuple[str, str]],
) -> Envio:
    """Segundo paso: plantilla del segmento, sesión nueva y contacto registrado."""
    repo = orq.repo
    momento = datetime.combine(hoy, time(9), ZONA)
    seg = segmentar(repo, customer_id)
    plantilla_id, texto = plantilla(seg.segmento.value, repo.cliente(customer_id).nombre)
    pasos += [("Segmento", f"{seg.segmento.value}: {seg.motivo}"), ("Plantilla", plantilla_id)]
    sesion = orq.iniciar(customer_id, conversacion_id, texto)
    repo.guardar_contacto(
        Contacto(
            contacto_id=f"CT-{conversacion_id}",
            customer_id=customer_id,
            campana_id=CAMPANA_ID,
            fecha=momento,
            canal="whatsapp",
            plantilla=plantilla_id,
            segmento_campana=seg.segmento.value,
            respondio=False,
            resultado="enviado",
        )
    )
    pasos.append(("Envío", "WhatsApp (simulado); se abre la ventana de 24 h"))
    return Envio(sesion=sesion, plantilla=texto, pasos=pasos)
