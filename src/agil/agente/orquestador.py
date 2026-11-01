"""Orquestador de turno (D31): lo que la Lambda router resuelve sin LLM, y luego el agente.

Orden por mensaje: botones (D22) → no contactar explícito (D13) → enmascarar la cédula (D24) →
moderación (D35) → verificación por código (D5) → contador y estratega (D16) → agente →
validador con un reintento (D4, D15) → render de placeholders (B4). Lo resuelto sin LLM entra al
agente como evento resumido en su siguiente turno (D22).
"""

import logging
import re
from collections.abc import Callable
from datetime import datetime

from opentelemetry import trace
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

from agil.agente.auxiliares import clasificar_momento, es_abusivo, resumir, tarjeta_estrategia
from agil.agente.config import Modelos
from agil.agente.hooks import Controles
from agil.agente.perfiles import cargar_perfil, prompt_sistema
from agil.agente.sesion import MAX_INTENTOS_CEDULA, MAX_STRIKES, Respuesta, Sesion
from agil.agente.tools import crear_tools
from agil.dominio.harness.identidad import enmascarar, extraer_digitos, verificar
from agil.dominio.harness.intenciones import Boton, pide_no_contacto
from agil.dominio.harness.placeholders import renderizar
from agil.dominio.harness.texto import sin_tildes
from agil.dominio.harness.validador import validar_salida
from agil.dominio.modelos import (
    AceptacionOferta,
    Cola,
    Handoff,
    Nota,
    PromesaPago,
    Segmento,
    SolicitudNoContacto,
)
from agil.dominio.reglas.calendario import ZONA
from agil.dominio.reglas.segmentacion import segmentar
from agil.dominio.repositorio.interfaz import Repositorio

log = logging.getLogger(__name__)

# Textos fijos: no pasan por el LLM. En producción serían plantillas aprobadas por legal.
TEXTOS = {
    "no_contactar": "Entendido. Registramos su solicitud y no le escribiremos más por este medio.",
    "abuso": "Quiero ayudarle, y para eso necesito que mantengamos el respeto. ¿Seguimos?",
    "abuso_cierre": "Vamos a cerrar esta conversación por ahora. Gracias.",
    "tope": "Vamos a dejar la conversación aquí por ahora. Gracias por su tiempo.",
    "fallo": "Disculpe, tuve un inconveniente. Un asesor continuará la conversación con usted.",
    "handoff": "Un asesor continuará la conversación con usted. Gracias por su paciencia.",
    "sin_tarjeta": "Esa opción ya no está disponible.",
}
_PIDE_CEDULA = re.compile(r"\bcedula\b|\bcuatro digitos\b", re.I)
_tracer = trace.get_tracer("agil.orquestador")


class Orquestador:
    def __init__(
        self,
        repo: Repositorio,
        modelos: Modelos,
        ahora: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo = repo
        self.modelos = modelos
        # El mundo del mock vive en su fecha de referencia; la hora es la real.
        self.ahora = ahora or (
            lambda: datetime.combine(repo.fecha_referencia, datetime.now(ZONA).time(), ZONA)
        )

    # --- Ciclo de vida ---

    def iniciar(
        self, customer_id: str, conversacion_id: str, plantilla: str | None = None
    ) -> Sesion:
        seg = segmentar(self.repo, customer_id)
        if seg.segmento is Segmento.excluido:
            raise ValueError(f"{customer_id} está excluido: lo atiende un humano ({seg.motivo})")
        perfil = cargar_perfil(seg.segmento)
        sesion = Sesion(
            conversacion_id=conversacion_id,
            customer_id=customer_id,
            segmento=seg.segmento,
            cola=seg.cola_escalamiento or Cola.basica,
            max_turnos=perfil.max_turnos,
            max_caracteres=perfil.max_caracteres,
        )
        if plantilla:
            sesion.transcripcion.append(("plantilla", plantilla))
            sesion.eventos.append(
                f"[sistema] Se envió la plantilla de primer contacto: «{plantilla}»"
            )
        return sesion

    def cerrar(self, sesion: Sesion, motivo: str) -> None:
        """Cierra y deja el resumen como nota para la próxima conversación (D34)."""
        sesion.cerrar(motivo)
        if not self.modelos.estratega:
            return
        resumen = resumir(self.modelos.estratega, sesion.transcripcion)
        if resumen:
            self.repo.guardar_nota(
                Nota(
                    nota_id=f"NT-{sesion.conversacion_id}-cierre",
                    customer_id=sesion.customer_id,
                    fecha=self.ahora(),
                    origen="sistema",
                    conversacion_id=sesion.conversacion_id,
                    texto=resumen.texto,
                    flags=resumen.flags,
                )
            )

    # --- Turno ---

    def atender(self, sesion: Sesion, texto: str = "", boton: Boton | None = None) -> Respuesta:
        """Un span por mensaje, sin el texto del cliente: resultado y pasos como atributos."""
        with _tracer.start_as_current_span("agil.turno") as span:
            span.set_attribute("session.id", sesion.conversacion_id)
            r = self._atender(sesion, texto, boton)
            span.set_attribute("agil.turno", sesion.turno)
            span.set_attribute("agil.tarjeta", r.tarjeta is not None)
            span.set_attribute("agil.cierre", sesion.motivo_cierre or "")
            return r

    def _atender(self, sesion: Sesion, texto: str, boton: Boton | None) -> Respuesta:
        if sesion.cerrada:
            return Respuesta(cerrada=True)
        if boton:
            return self._boton(sesion, boton)
        if pide_no_contacto(texto):
            return self._no_contactar(sesion, texto)

        # Ninguna cédula llega a un modelo; sin verificar, ningún dígito (D24). Solo cuenta como
        # intento si el agente la pidió ("1500" es ambiguo).
        digitos = None if sesion.verificada else extraer_digitos(texto)
        visible = enmascarar(texto, solo_cedula=sesion.verificada)
        sesion.transcripcion.append(("cliente", visible))

        if self.modelos.moderador and es_abusivo(self.modelos.moderador, visible):
            trace.get_current_span().add_event("moderacion", {"abusivo": True})
            return self._abuso(sesion)
        if digitos and sesion.cedula_pedida:
            self._verificar(sesion, digitos)
        return self._turno_agente(sesion, f"Cliente: {visible}")

    def _turno_agente(self, sesion: Sesion, linea_cliente: str) -> Respuesta:
        sesion.turno += 1
        if sesion.turno > sesion.max_turnos:
            return self._cierre_fijo(sesion, "tope", TEXTOS["tope"])
        sesion.contexto = self._contexto(sesion)
        mensaje = "\n".join([*sesion.eventos, linea_cliente])
        sesion.eventos = []
        tarjeta_previa = sesion.tarjeta
        try:
            texto = self._invocar(sesion, mensaje)
        except Exception:
            log.exception("Fallo del agente")
            texto = None
        if texto is None:
            sesion.tarjeta = None
            if sesion.cerrada:  # una tool ya cerró (handoff o no contacto): solo falló el texto
                motivo = sesion.motivo_cierre
                return self._cierre_fijo(sesion, motivo, TEXTOS.get(motivo, TEXTOS["handoff"]))
            self._handoff_fallo(sesion)  # fallo nuestro: humano (D15)
            return self._cierre_fijo(sesion, "fallo", TEXTOS["fallo"])

        if _PIDE_CEDULA.search(sin_tildes(texto)) and not sesion.verificada:
            sesion.cedula_pedida = True
        final = renderizar(texto, sesion.valores)
        sesion.transcripcion.append(("agente", texto))
        tarjeta = sesion.tarjeta if sesion.tarjeta is not tarjeta_previa else None
        if sesion.cerrada:
            self.cerrar(sesion, sesion.motivo_cierre or "agente")
        return Respuesta(mensajes=[final], tarjeta=tarjeta, cerrada=sesion.cerrada)

    def _contexto(self, sesion: Sesion) -> list[str]:
        lineas = [f"[contexto] Turno {sesion.turno} de {sesion.max_turnos}."]
        if sesion.max_turnos - sesion.turno < 3:
            lineas.append(
                "[contexto] Quedan pocos turnos: propone cerrar (link, promesa o asesor)."
            )
        if self.modelos.estratega:
            momento = clasificar_momento(self.modelos.estratega, sesion.transcripcion)
            tarjeta = momento and tarjeta_estrategia(momento)
            if tarjeta:
                lineas.append(f"[estrategia: {momento.value}] {tarjeta}")
        return lineas

    def _invocar(self, sesion: Sesion, mensaje: str) -> str | None:
        """Respuesta validada del agente, o None si falla dos veces (D4, D15)."""
        agente = self._agente(sesion)
        texto = str(agente(mensaje)).strip()
        v = validar_salida(texto, set(sesion.valores), sesion.max_caracteres)
        trace.get_current_span().add_event("validador", {"ok": v.ok, "motivo": v.motivo or ""})
        if not v.ok and not sesion.cerrada:
            fallido = agente.messages[-1]
            sesion.contexto = []
            texto = str(agente(f"[sistema] Tu respuesta no se envió: {v.motivo} Reescríbela."))
            texto = texto.strip()
            v = validar_salida(texto, set(sesion.valores), sesion.max_caracteres)
            # El intento fallido y la corrección no quedan en el historial.
            i = next((i for i, m in enumerate(agente.messages) if m is fallido), None)
            if i is not None:
                del agente.messages[i : i + 2]
        sesion.historial = list(agente.messages)
        return texto if v.ok else None

    def _agente(self, sesion: Sesion) -> Agent:
        cliente = self.repo.cliente(sesion.customer_id)
        perfil = cargar_perfil(sesion.segmento)
        return Agent(
            model=self.modelos.agente,
            system_prompt=prompt_sistema(perfil, cliente, self.ahora()),
            tools=crear_tools(self.repo, sesion, self.ahora),
            hooks=[Controles(self.repo, sesion)],
            messages=sesion.historial,
            conversation_manager=SlidingWindowConversationManager(window_size=20),
            callback_handler=None,
            trace_attributes={
                "session.id": sesion.conversacion_id,
                "agil.segmento": sesion.segmento.value,
            },
        )

    # --- Lo que resuelve el código ---

    def _verificar(self, sesion: Sesion, digitos: str) -> None:
        """El número nunca llega al LLM; solo el resultado (D24)."""
        cliente = self.repo.cliente(sesion.customer_id)
        if verificar(cliente, digitos):
            sesion.verificada = True
            sesion.cedula_pedida = False
            evento = "[sistema] Verificación de cédula correcta."
            notas = self.repo.notas(sesion.customer_id)[-3:]
            if notas:
                evento += " Notas de conversaciones anteriores: " + " | ".join(
                    n.texto for n in notas
                )
        else:
            sesion.intentos_cedula += 1
            evento = (
                f"[sistema] Verificación fallida (intento {sesion.intentos_cedula} de "
                f"{MAX_INTENTOS_CEDULA})."
            )
            if sesion.intentos_cedula >= MAX_INTENTOS_CEDULA:
                sesion.cedula_pedida = False
                evento += " No la pidas más; ofrece un asesor."
        sesion.eventos.append(evento)

    def _boton(self, sesion: Sesion, boton: Boton) -> Respuesta:
        tarjeta = sesion.tarjeta
        sesion.tarjeta = None
        if tarjeta is None:
            return Respuesta(mensajes=[TEXTOS["sin_tarjeta"]])
        que = f"oferta {tarjeta.oferta_id}" if tarjeta.tipo == "oferta" else "promesa de pago"
        if boton is Boton.confirmar:
            self._registrar(sesion, tarjeta)
            sesion.eventos.append(f"[sistema] El cliente confirmó la tarjeta ({que}): registrada.")
        else:
            sesion.eventos.append(f"[sistema] El cliente canceló la tarjeta ({que}).")
        sesion.transcripcion.append(("cliente", f"[botón {boton.name}: {que}]"))
        return self._turno_agente(sesion, f"Cliente: [tocó «{boton.name}»]")

    def _registrar(self, sesion: Sesion, tarjeta) -> None:
        sufijo = f"{sesion.conversacion_id}-{len(sesion.escrituras)}"
        if tarjeta.tipo == "oferta":
            sesion.oferta_aceptada = sesion.condiciones[tarjeta.oferta_id]
            self.repo.guardar_aceptacion(
                AceptacionOferta(
                    aceptacion_id=f"AC-{sufijo}",
                    customer_id=sesion.customer_id,
                    oferta_id=tarjeta.oferta_id,
                    monto_base=sesion.oferta_aceptada.monto_base,
                    creada=self.ahora(),
                )
            )
        else:
            self.repo.guardar_promesa(
                PromesaPago(
                    promesa_id=f"PP-{sufijo}",
                    customer_id=sesion.customer_id,
                    fecha_promesa=tarjeta.fecha,
                    monto=tarjeta.monto,
                    oferta_id=tarjeta.oferta_id,
                    creada=self.ahora(),
                )
            )
        sesion.escrituras.add(sufijo)

    def _no_contactar(self, sesion: Sesion, texto: str) -> Respuesta:
        """Frase explícita (D13): se deriva y pausa sin LLM; el evento llega al resumen."""
        self.repo.guardar_solicitud_no_contacto(
            SolicitudNoContacto(
                solicitud_id=f"NC-{sesion.conversacion_id}",
                customer_id=sesion.customer_id,
                texto=texto,
                creada=self.ahora(),
            )
        )
        self.repo.pausar_whatsapp(sesion.customer_id, self.ahora().date())
        sesion.transcripcion.append(("cliente", enmascarar(texto, solo_cedula=False)))
        sesion.transcripcion.append(
            ("sistema", "Solicitud de no contacto registrada; WhatsApp pausado.")
        )
        return self._cierre_fijo(sesion, "no_contactar", TEXTOS["no_contactar"])

    def _abuso(self, sesion: Sesion) -> Respuesta:
        sesion.strikes += 1
        if sesion.strikes >= MAX_STRIKES:
            return self._cierre_fijo(sesion, "abuso", TEXTOS["abuso_cierre"])
        sesion.eventos.append(
            f"[sistema] Mensaje abusivo del cliente (strike {sesion.strikes} de {MAX_STRIKES}); "
            "se respondió con el texto fijo."
        )
        sesion.transcripcion.append(("agente", TEXTOS["abuso"]))
        return Respuesta(mensajes=[TEXTOS["abuso"]])

    def _handoff_fallo(self, sesion: Sesion) -> None:
        self.repo.guardar_handoff(
            Handoff(
                handoff_id=f"HO-{sesion.conversacion_id}-fallo",
                customer_id=sesion.customer_id,
                cola=sesion.cola,
                motivo="fallo_agente",
                resumen="El agente no pudo generar una respuesta válida.",
                creado=self.ahora(),
            )
        )

    def _cierre_fijo(self, sesion: Sesion, motivo: str, texto: str) -> Respuesta:
        sesion.transcripcion.append(("agente", texto))
        self.cerrar(sesion, motivo)
        return Respuesta(mensajes=[texto], cerrada=True)
