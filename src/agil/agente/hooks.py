"""Controles deterministas sobre el bucle de Strands (harness_del_agente, framework_strands).

Cada bloqueo explica el motivo: el modelo lo recibe como resultado de la tool y no repite la acción.
"""

from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from agil.agente.sesion import MAX_INTENTOS_CEDULA, Sesion
from agil.agente.tools import SENSIBLES
from agil.dominio.reglas.ofertas import validar_oferta
from agil.dominio.repositorio.interfaz import Repositorio

MAX_PASOS = 6  # tools por turno

VERIFICACION_PENDIENTE = (
    "Verificación pendiente: antes de esta tool pide al cliente los últimos cuatro dígitos de su "
    "cédula. Nunca pidas la cédula completa."
)
VERIFICACION_BLOQUEADA = (
    "Verificación bloqueada tras varios intentos fallidos: no la pidas más. Ofrece un asesor."
)


class Controles(HookProvider):
    def __init__(self, repo: Repositorio, sesion: Sesion, max_pasos: int = MAX_PASOS) -> None:
        self.repo = repo
        self.sesion = sesion
        self.max_pasos = max_pasos
        self.pasos = 0
        self.bloque: dict | None = None

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeInvocationEvent, self.inyectar_contexto)
        registry.add_callback(BeforeToolCallEvent, self.antes_de_tool)
        registry.add_callback(AfterInvocationEvent, self.quitar_contexto)

    def inyectar_contexto(self, event: BeforeInvocationEvent) -> None:
        """Contador de turnos y tarjeta del estratega (D16), delante del mensaje del cliente."""
        self.pasos = 0
        self.bloque = None
        if not self.sesion.contexto or not event.messages:
            return
        *previos, ultimo = event.messages
        self.bloque = {"text": "\n".join(self.sesion.contexto)}
        event.messages = [*previos, {**ultimo, "content": [self.bloque, *ultimo["content"]]}]

    def quitar_contexto(self, event: AfterInvocationEvent) -> None:
        """El contexto es efímero: no se acumula en el historial ni gasta tokens en otros turnos."""
        for mensaje in event.agent.messages:
            mensaje["content"] = [b for b in mensaje["content"] if b != self.bloque]

    def antes_de_tool(self, event: BeforeToolCallEvent) -> None:
        nombre = event.tool_use["name"]
        self.pasos += 1
        if self.pasos > self.max_pasos:
            event.cancel_tool = "Límite de pasos del turno: responde ya al cliente."
            return
        if nombre in SENSIBLES and not self.sesion.verificada:
            bloqueada = self.sesion.intentos_cedula >= MAX_INTENTOS_CEDULA
            self.sesion.cedula_pedida = not bloqueada
            event.cancel_tool = VERIFICACION_BLOQUEADA if bloqueada else VERIFICACION_PENDIENTE
            return
        oferta_id = (event.tool_use.get("input") or {}).get("oferta_id")
        if nombre in ("aceptar_oferta", "registrar_promesa_pago") and oferta_id is not None:
            s = self.sesion
            v = validar_oferta(self.repo, s.customer_id, s.segmento, oferta_id)
            if not v.ok:
                event.cancel_tool = v.motivo
