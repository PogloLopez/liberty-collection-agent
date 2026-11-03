"""Lambdas de la nube (D46). Una sola imagen con tres handlers, que el stack elige con su comando:

- `handler`: la API (FastAPI + Mangum) detrás de la URL de la función y de CloudFront.
- `filtro` y `envio`: los dos pasos de la campaña en Step Functions (botón "Que sean las 9 AM").

Variables que pone el stack: TABLA, RUNTIME_ARN, CAMPANA_ARN, CODIGO_ACCESO, LLM_PROVIDER,
GUARDRAIL_ID y GUARDRAIL_VERSION (siempre) y, con groq u openrouter, LLM_API_KEY_PARAM (D50).
"""

import json
import os
import uuid
from datetime import datetime
from functools import cache
from typing import Any

from fastapi import HTTPException
from mangum import Mangum
from opentelemetry import trace

from agil.agente.config import Configuracion, Modelos, crear_modelos
from agil.agente.orquestador import Orquestador
from agil.app.api import Backend, montar
from agil.app.campana import enviar, filtrar
from agil.app.sesiones import SesionesDynamo
from agil.dominio.reglas.calendario import ZONA
from agil.dominio.repositorio.dynamo import RepositorioDynamo, reiniciar
from agil.nube.agente_remoto import OrquestadorRemoto, invocador_runtime
from agil.nube.recursos import cliente, cliente_runtime, tabla

_tracer = trace.get_tracer("agil.nube")


@cache
def _cfg() -> Configuracion:
    return Configuracion()


@cache
def _modelos() -> Modelos:
    """En la Lambda solo se usa el estratega, para el resumen de los cierres sin agente (D34)."""
    return crear_modelos(_cfg())


def _tabla() -> Any:
    return tabla(os.environ["TABLA"])


def _nuevo_id() -> str:
    """Hora y un sufijo al azar: dos campañas a la vez no chocan (en la nube no hay candado) y la
    cartera sigue ordenada por hora."""
    return f"CV-{datetime.now(ZONA):%H%M%S}-{uuid.uuid4().hex[:4]}"


def _campana(repo: RepositorioDynamo, customer_id: str, conversacion_id: str) -> dict:
    """Express síncrono: la API espera el resultado de los dos pasos para mostrar la plantilla."""
    with _tracer.start_as_current_span("agil.campana") as span:
        span.set_attribute("session.id", conversacion_id)
        r = cliente("stepfunctions").start_sync_execution(
            stateMachineArn=os.environ["CAMPANA_ARN"],
            input=json.dumps({"customer_id": customer_id, "conversacion_id": conversacion_id}),
        )
        span.set_attribute("agil.estado", r["status"])
        if r["status"] != "SUCCEEDED":
            raise HTTPException(502, f"La campaña terminó en {r['status']}")
        return json.loads(r["output"])


def _reiniciar(t: Any) -> None:
    with _tracer.start_as_current_span("agil.reiniciar") as span:
        span.set_attribute("agil.items", reiniciar(t))


def backend() -> Backend:
    t = _tabla()
    invocar = invocador_runtime(cliente_runtime(), os.environ["RUNTIME_ARN"])
    return Backend(
        repo=lambda: RepositorioDynamo(t),
        orquestador=lambda r: OrquestadorRemoto(r, _modelos(), invocar=invocar),
        sesiones=SesionesDynamo(t),
        campana=_campana,
        reiniciar=lambda: _reiniciar(t),
        nuevo_id=_nuevo_id,
    )


def handler(evento: dict, contexto: Any) -> dict:
    return _mangum()(evento, contexto)


@cache
def _mangum() -> Mangum:
    app = montar(backend(), _cfg().modo_demo, codigo=os.environ.get("CODIGO_ACCESO"))
    return Mangum(app, lifespan="off")


def filtro(evento: dict, _contexto: Any) -> dict:
    """Paso 1 de la campaña. Devuelve la forma del Envio para que, si no pasa, sea el resultado."""
    with _tracer.start_as_current_span("agil.campana.filtro") as span:
        span.set_attribute("session.id", evento["conversacion_id"])
        repo = RepositorioDynamo(_tabla())
        ok, pasos = filtrar(repo, evento["customer_id"], repo.fecha_referencia, _cfg().modo_demo)
        span.set_attribute("agil.enviable", ok)
        return {**evento, "ok": ok, "pasos": pasos, "sesion": None, "plantilla": None}


def envio(evento: dict, _contexto: Any) -> dict:
    """Paso 2: plantilla, sesión y contacto; la sesión queda en DynamoDB para la conversación."""
    with _tracer.start_as_current_span("agil.campana.envio") as span:
        span.set_attribute("session.id", evento["conversacion_id"])
        repo = RepositorioDynamo(_tabla())
        e = enviar(
            Orquestador(repo, _modelos()),
            evento["customer_id"],
            evento["conversacion_id"],
            repo.fecha_referencia,
            [tuple(p) for p in evento["pasos"]],
        )
        SesionesDynamo(_tabla()).guardar(e.sesion)
        return e.model_dump(mode="json")
