"""Controles deterministas sobre el bucle de Strands (harness_del_agente, framework_strands).

Cada bloqueo explica el motivo: el modelo lo recibe como resultado de la tool y no repite la acción.
"""

from collections.abc import Callable
from datetime import datetime

from opentelemetry import trace
from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
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
INSISTENCIA = 2  # tools canceladas por el tope antes de cortar el bucle

TOPE_DE_PASOS = (
    "Límite de pasos del turno: no llames más tools. Responde ya al cliente: resume lo que sí se "
    "completó en este turno y lo que quedó cancelado y, si falta algo, pídele que lo retome en su "
    "siguiente mensaje."
)
# Si el modelo insiste tras el tope, el turno termina con este texto fijo (también en el historial).
RESPUESTA_TOPE = (
    "Avancé con una parte de su solicitud. Escríbame de nuevo y terminamos lo que falta."
)

VERIFICACION_PENDIENTE = (
    "Verificación pendiente: antes de esta tool pide al cliente los últimos cuatro dígitos de su "
    "cédula. Nunca pidas la cédula completa."
)
VERIFICACION_BLOQUEADA = (
    "Verificación bloqueada tras varios intentos fallidos: no la pidas más. Ofrece un asesor."
)


class Controles(HookProvider):
    def __init__(
        self,
        repo: Repositorio,
        sesion: Sesion,
        ahora: Callable[[], datetime],
        max_pasos: int = MAX_PASOS,
    ) -> None:
        self.repo = repo
        self.sesion = sesion
        self.ahora = ahora
        self.max_pasos = max_pasos
        self.pasos = 0
        self.agotado = False  # el modelo insistió tras el tope: el orquestador usa su texto fijo
        self.tarjeta_enviada = False  # una tool creó tarjeta: el turno termina con ella (T1)
        self.bloque: dict | None = None
        self._tarjeta_previa = None

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeInvocationEvent, self.inyectar_contexto)
        registry.add_callback(BeforeToolCallEvent, self.antes_de_tool)
        registry.add_callback(AfterToolCallEvent, self.despues_de_tool)
        registry.add_callback(AfterInvocationEvent, self.quitar_contexto)

    def inyectar_contexto(self, event: BeforeInvocationEvent) -> None:
        """Contador de turnos y tarjeta del estratega (D16), después del mensaje del cliente: así
        el mensaje queda igual al quitarlo y el caché por prefijo del proveedor no se corta."""
        self.pasos = 0
        self.agotado = False
        self.tarjeta_enviada = False
        self._tarjeta_previa = self.sesion.tarjeta
        self.bloque = None
        if not self.sesion.contexto or not event.messages:
            return
        *previos, ultimo = event.messages
        self.bloque = {"text": "\n".join(self.sesion.contexto)}
        event.messages = [*previos, {**ultimo, "content": [*ultimo["content"], self.bloque]}]

    def quitar_contexto(self, event: AfterInvocationEvent) -> None:
        """El contexto es efímero: no se acumula en el historial ni gasta tokens en otros turnos."""
        for mensaje in event.agent.messages:
            mensaje["content"] = [b for b in mensaje["content"] if b != self.bloque]

    def antes_de_tool(self, event: BeforeToolCallEvent) -> None:
        nombre = event.tool_use["name"]
        self.pasos += 1
        if self.pasos > self.max_pasos:
            event.cancel_tool = TOPE_DE_PASOS
            if self.pasos > self.max_pasos + INSISTENCIA:
                self.agotado = True
                event.agent.cancel(message=RESPUESTA_TOPE)
            return
        self.sesion.vencer_verificacion(self.ahora())
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

    def despues_de_tool(self, event: AfterToolCallEvent) -> None:
        """La tarjeta se basta sola (T1): con ella termina el turno, sin otra llamada al modelo. El
        historial guarda qué se envió, sin cifras (el texto completo queda en la transcripción)."""
        tarjeta = self.sesion.tarjeta
        if tarjeta is not None and tarjeta is not self._tarjeta_previa:
            self.tarjeta_enviada = True
            trace.get_current_span().add_event("tarjeta_enviada", {"tipo": tarjeta.tipo})
            aviso = f"[tarjeta enviada: {tarjeta.descripcion}; espera el botón del cliente]"
            event.agent.cancel(message=aviso, after_current_tools=True)
