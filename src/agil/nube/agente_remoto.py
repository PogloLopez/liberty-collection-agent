"""El turno del agente cruza de la Lambda al AgentCore Runtime (D46).

La Lambda corre el orquestador: lo determinista (botones, no contactar, cédula, sin sentido, pedido
de asesor) se resuelve sin despertar al agente. Solo `_turno_agente` viaja al Runtime con la sesión
serializada, y vuelve con la sesión actualizada, los pasos y la respuesta.
"""

import json
from collections.abc import Callable
from typing import Any

from opentelemetry import trace

from agil.agente.orquestador import Orquestador
from agil.agente.sesion import Respuesta, Sesion

Invocar = Callable[[dict[str, Any]], dict[str, Any]]
_tracer = trace.get_tracer("agil.nube")


def pedido(sesion: Sesion, linea_cliente: str) -> dict[str, Any]:
    """Lo que viaja al Runtime; `recien_verificada` no se guarda con la sesión, pero cambia el
    turno."""
    return {
        "sesion": sesion.model_dump(mode="json"),
        "recien_verificada": sesion.recien_verificada,
        "linea_cliente": linea_cliente,
    }


def atender_pedido(orq: Orquestador, datos: dict[str, Any]) -> dict[str, Any]:
    """Lado del Runtime: corre el turno del agente tal como en local."""
    sesion = Sesion.model_validate(datos["sesion"])
    sesion.recien_verificada = datos["recien_verificada"]
    with _tracer.start_as_current_span("agil.turno") as span:  # el mismo span que en local
        span.set_attribute("session.id", sesion.conversacion_id)
        r = orq._turno_agente(sesion, datos["linea_cliente"])
        span.set_attribute("agil.turno", sesion.turno)
    return {
        "sesion": sesion.model_dump(mode="json"),
        "pasos": sesion.pasos,
        "respuesta": r.model_dump(mode="json"),
    }


class OrquestadorRemoto(Orquestador):
    """Lado de la Lambda: el mismo orquestador, con el turno del agente en el Runtime."""

    def __init__(self, *args, invocar: Invocar, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.invocar = invocar

    def _turno_agente(self, sesion: Sesion, linea_cliente: str) -> Respuesta:
        datos = self.invocar(pedido(sesion, linea_cliente))
        nueva = Sesion.model_validate(datos["sesion"])
        for campo in Sesion.model_fields:  # en el sitio: `atender` sigue con el mismo objeto
            if campo != "pasos":
                setattr(sesion, campo, getattr(nueva, campo))
        sesion.recien_verificada = False
        sesion.pasos.extend(tuple(p) for p in datos["pasos"])
        return Respuesta.model_validate(datos["respuesta"])


def invocador_runtime(cliente: Any, runtime_arn: str) -> Invocar:
    """`cliente`: el cliente `bedrock-agentcore` de la SDK. Una sesión del Runtime por conversación:
    el id debe tener al menos 33 caracteres (guía de AgentCore)."""

    def invocar(datos: dict[str, Any]) -> dict[str, Any]:
        conversacion_id = datos["sesion"]["conversacion_id"]
        with _tracer.start_as_current_span("agil.runtime.invocar") as span:
            span.set_attribute("session.id", conversacion_id)
            r = cliente.invoke_agent_runtime(
                agentRuntimeArn=runtime_arn,
                runtimeSessionId=f"agil-conversacion-{conversacion_id}".ljust(33, "0"),
                payload=json.dumps(datos).encode(),
                contentType="application/json",
                accept="application/json",
            )
            span.set_attribute("agil.estado_http", r.get("statusCode", 0))
            return json.loads(r["response"].read())

    return invocar
