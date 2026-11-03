"""Orquestador de turno (D31): lo que la Lambda router resuelve sin LLM, y luego el agente.

Orden por mensaje: botones (D22) → no contactar explícito (D13) → enmascarar la cédula (D24) →
moderación (D35) → verificación por código (D5) → pedido de asesor (D45) → contador y estratega
(D16) → agente → validador con un reintento (D4, D15) → render de placeholders (B4). Lo resuelto
sin LLM entra al agente como evento resumido en su siguiente turno (D22).
"""

import logging
import re
from collections.abc import Callable
from datetime import date, datetime, time
from decimal import Decimal

from opentelemetry import trace
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

from agil.agente import formato
from agil.agente.auxiliares import clasificar_momento, es_abusivo, resumir, tarjeta_estrategia
from agil.agente.config import Modelos
from agil.agente.hooks import RESPUESTA_TOPE, Controles
from agil.agente.perfiles import cargar_perfil, linea_hora, prompt_sistema
from agil.agente.sesion import (
    MAX_FALLOS_SEGUIDOS,
    MAX_INTENTOS_CEDULA,
    MAX_PEDIDOS_HUMANO,
    MAX_STRIKES,
    Respuesta,
    Sesion,
)
from agil.agente.tools import (
    cifras_oferta,
    cifras_saldo,
    crear_tools,
    escalera,
    link_pago,
    prefijo,
)
from agil.dominio.harness.identidad import enmascarar, extraer_digitos, verificar
from agil.dominio.harness.intenciones import Boton, pide_humano, pide_no_contacto, sin_sentido
from agil.dominio.harness.placeholders import renderizar
from agil.dominio.harness.texto import sin_tildes
from agil.dominio.harness.validador import a_whatsapp, validar_salida
from agil.dominio.modelos import (
    AceptacionOferta,
    Cola,
    EstadoCuenta,
    Handoff,
    Nota,
    PromesaPago,
    Segmento,
    SolicitudNoContacto,
    Validacion,
)
from agil.dominio.reglas.calculos import estado_cuenta
from agil.dominio.reglas.calendario import ZONA
from agil.dominio.reglas.ofertas import condiciones, ofertas_elegibles
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
    "respuesta_segura": "Disculpe, ¿me lo puede repetir?",
    "sin_sentido": "No entendí su mensaje. ¿Me lo escribe de nuevo?",
    "sin_sentido_cierre": (
        "Vamos a cerrar esta conversación por ahora. Si necesita ayuda, escríbanos."
    ),
    "cedula_no_coincide": (
        "Esos dígitos no coinciden con los de la cuenta. Revíselos y escríbalos de nuevo: solo los "
        "cuatro números, sin puntos ni guiones."
    ),
    "cedula_bloqueada": (
        "Por seguridad no puedo darle datos de la cuenta por aquí. Un asesor le ayudará a validar "
        "su identidad."
    ),
    "pasos": RESPUESTA_TOPE,
}
_PIDE_CEDULA = re.compile(r"\bcedula\b|\bcuatro digitos\b", re.I)
# Preguntas que piden confirmar en texto lo que confirma una tarjeta ("¿Confirma…?",
# "¿Lo registro?"); no "¿Ya registró su pago?" ni la de los cuatro dígitos de la cédula.
_PREGUNTA = re.compile(r"[^.!?]*\?")
_CONFIRMA = re.compile(
    r"\b(?:confirma(?:mos)?|confirmo|l[ao] registr(?:o|amos)|registramos|procedo|procedemos)\b",
    re.I,
)
_USA_LA_TARJETA = (
    "No pidas confirmación en texto. Si el cliente ya eligió una oferta o un día, llama a "
    "aceptar_oferta o registrar_promesa_pago: la tarjeta con botones es la confirmación. Si aún no "
    "eligió, propón la opción sin pedirle que confirme."
)
REINTENTOS = 2
HORA_DEMO = time(9)  # la del botón "Que sean las 9 AM" (D47)
_ARRANQUE = datetime.now(ZONA)


def reloj_demo(fecha: date) -> datetime:
    """La fecha del mock a las 9:00 más lo que lleva vivo el proceso: el saludo y el filtro de
    horario no dependen de quien prueba, y el tiempo sigue avanzando (D47). En producción se
    pasaría el reloj real."""
    return datetime.combine(fecha, HORA_DEMO, ZONA) + (datetime.now(ZONA) - _ARRANQUE)


_tracer = trace.get_tracer("agil.orquestador")


def _pide_confirmacion(texto: str) -> bool:
    preguntas = _PREGUNTA.findall(sin_tildes(texto))
    return any(_CONFIRMA.search(p) and not _PIDE_CEDULA.search(p) for p in preguntas)


class Orquestador:
    def __init__(
        self,
        repo: Repositorio,
        modelos: Modelos,
        ahora: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo = repo
        self.modelos = modelos
        self.ahora = ahora or (lambda: reloj_demo(repo.fecha_referencia))

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
            sesion.pasos = []
            r = self._atender(sesion, texto, boton)
            r.pasos, sesion.pasos = sesion.pasos, []
            r.pide_cedula = sesion.cedula_pedida and not sesion.verificada and not sesion.cerrada
            span.set_attribute("agil.turno", sesion.turno)
            span.set_attribute("agil.tarjeta", r.tarjeta is not None)
            span.set_attribute("agil.cierre", sesion.motivo_cierre or "")
            span.set_attribute("agil.pide_cedula", r.pide_cedula)
            return r

    def _atender(self, sesion: Sesion, texto: str, boton: Boton | None) -> Respuesta:
        if sesion.cerrada:
            sesion.paso("Sesión cerrada", "no se procesa el mensaje")
            return Respuesta(cerrada=True)
        if sesion.vencer_verificacion(self.ahora()):  # también ante un botón: anula la tarjeta
            sesion.paso("Verificación vencida", "pasaron 12 horas: se pide de nuevo")
            sesion.eventos.append(
                "[sistema] La verificación venció (12 horas): pide de nuevo los cuatro dígitos "
                "antes de dar datos de la cuenta."
            )
        self._refrescar_cifras(sesion)
        if boton:
            return self._boton(sesion, boton)
        if pide_no_contacto(texto):
            return self._no_contactar(sesion, texto)
        if sesion.tarjeta:  # T2: escribió en vez de tocar un botón; la tarjeta sigue vigente
            trace.get_current_span().add_event("tarjeta_pendiente")
            sesion.paso("Tarjeta pendiente", "escribió sin tocar los botones")
            aviso = (
                "[sistema] El cliente escribió sin responder la tarjeta pendiente "
                f"({sesion.tarjeta.descripcion})."
            )
            if aviso not in sesion.eventos:
                sesion.eventos.append(aviso)

        # Ninguna cédula llega a un modelo; sin verificar, ningún dígito (D24). Solo cuenta como
        # intento si el agente la pidió ("1500" es ambiguo).
        digitos = None if sesion.verificada else extraer_digitos(texto, sesion.cedula_pedida)
        visible = enmascarar(texto, solo_cedula=sesion.verificada)
        sesion.transcripcion.append(("cliente", visible))
        if visible != texto:
            sesion.paso("Datos enmascarados", "ningún dígito de la cédula llega a un modelo")

        if not digitos and sin_sentido(visible):  # antes de cualquier modelo (D40)
            return self._sin_sentido(sesion)
        sesion.sin_sentido = 0
        if self.modelos.moderador:
            abusivo = es_abusivo(self.modelos.moderador, visible)
            sesion.paso("Moderación", "abusivo" if abusivo else "sin problemas")
            if abusivo:
                trace.get_current_span().add_event("moderacion", {"abusivo": True})
                return self._abuso(sesion)
        if digitos and sesion.cedula_pedida and (fallo := self._verificar(sesion, digitos)):
            return fallo
        if pide_humano(visible) and (r := self._pide_humano(sesion)):  # tras la moderación (D45)
            return r
        return self._turno_agente(sesion, f"Cliente: {visible}")

    def _turno_agente(self, sesion: Sesion, linea_cliente: str) -> Respuesta:
        sesion.turno += 1
        if sesion.turno > sesion.max_turnos:
            return self._cierre_fijo(sesion, "tope", TEXTOS["tope"])
        # Un intento de cédula solo cuenta en el mensaje que sigue a la petición: "15-02" dos turnos
        # después es una fecha. El turno vuelve a encenderlo si la pide de nuevo.
        sesion.cedula_pedida = False
        sesion.paso("Contador", f"turno {sesion.turno} de {sesion.max_turnos}")
        sesion.contexto = self._contexto(sesion)
        mensaje = "\n".join([*sesion.eventos, linea_cliente])
        sesion.eventos = []
        tarjeta_previa = sesion.tarjeta
        n = len(sesion.historial)
        try:
            texto = self._invocar(sesion, mensaje)
        except Exception:
            log.exception("Fallo del agente")
            del sesion.historial[n:]  # sin un toolUse a medias que rompa los turnos siguientes
            texto = None
        if texto is None:
            sesion.tarjeta = None
            if sesion.cerrada:  # una tool ya cerró (handoff o no contacto): solo falló el texto
                motivo = sesion.motivo_cierre
                return self._cierre_fijo(sesion, motivo, TEXTOS.get(motivo, TEXTOS["handoff"]))
            # Fallo nuestro (D15): texto seguro; tres turnos fallidos seguidos van al asesor (D40).
            sesion.fallos_seguidos += 1
            if sesion.fallos_seguidos >= MAX_FALLOS_SEGUIDOS:
                self._handoff(
                    sesion,
                    "fallo",
                    "fallo_agente",
                    "El agente no pudo generar una respuesta válida.",
                )
                return self._cierre_fijo(sesion, "fallo", TEXTOS["fallo"])
            sesion.paso(
                "Respuesta segura",
                f"texto fijo (turno fallido {sesion.fallos_seguidos} de {MAX_FALLOS_SEGUIDOS})",
            )
            sesion.transcripcion.append(("agente", TEXTOS["respuesta_segura"]))
            return Respuesta(mensajes=[TEXTOS["respuesta_segura"]])
        sesion.fallos_seguidos = 0

        tarjeta = sesion.tarjeta if sesion.tarjeta is not tarjeta_previa else None
        if texto == "" and tarjeta is not None:  # la tarjeta se basta sola (T1)
            sesion.paso("Tarjeta con botones", f"{tarjeta.descripcion}; termina el turno")
            sesion.transcripcion.append(("agente", f"[tarjeta] {tarjeta.texto}"))
            return Respuesta(tarjeta=tarjeta)
        if _PIDE_CEDULA.search(sin_tildes(texto)) and not sesion.verificada:
            sesion.cedula_pedida = True
        final = renderizar(a_whatsapp(texto), sesion.valores)
        sesion.transcripcion.append(("agente", texto))
        if sesion.cerrada:
            sesion.paso("Cierre", sesion.motivo_cierre or "agente")
            self.cerrar(sesion, sesion.motivo_cierre or "agente")
        return Respuesta(mensajes=[final], tarjeta=tarjeta, cerrada=sesion.cerrada)

    def _contexto(self, sesion: Sesion) -> list[str]:
        lineas = [
            linea_hora(self.ahora()),
            f"[contexto] Turno {sesion.turno} de {sesion.max_turnos}.",
        ]
        if sesion.max_turnos - sesion.turno < 3:
            lineas.append(
                "[contexto] Quedan pocos turnos: propone cerrar (link, promesa o asesor)."
            )
        if sesion.acuerdos and sesion.verificada:  # vencida la verificación, no se revela (D5)
            lineas.append(
                f"[contexto] Ya registrado en esta conversación: {'; '.join(sesion.acuerdos)}. "
                "No lo vuelvas a ofrecer ni pidas confirmarlo."
            )
        recien, sesion.recien_verificada = sesion.recien_verificada, False
        if self.modelos.estratega and sesion.verificada and not recien:  # D40, D41
            momento = clasificar_momento(self.modelos.estratega, sesion.transcripcion)
            tarjeta = momento and tarjeta_estrategia(momento)
            nombre = momento.value if momento else "sin clasificar"
            sesion.paso("Estratega", f"{nombre}: {tarjeta}" if tarjeta else nombre)
            if tarjeta:  # una sugerencia, no una orden (D41)
                lineas.append(
                    f"[estrategia sugerida: {nombre}] Si encaja con lo que dijo: {tarjeta}"
                )
        elif self.modelos.estratega:
            motivo = "recién verificado: retoma lo pedido" if recien else "sin verificar"
            sesion.paso("Estratega", f"omitido: {motivo}")
        return lineas

    def _invocar(self, sesion: Sesion, mensaje: str) -> str | None:
        """Respuesta validada del agente; "" si el turno terminó con una tarjeta (T1) y None si
        falla tras 1 + REINTENTOS intentos (D4, D15, D40)."""
        agente, controles = self._agente(sesion)
        texto = str(agente(mensaje)).strip()
        if controles.agotado:  # el modelo siguió pidiendo tools tras el tope (K1)
            trace.get_current_span().add_event("tope_pasos", {"pasos": controles.pasos})
            sesion.historial = list(agente.messages)
            return None if sesion.cerrada else TEXTOS["pasos"]
        if controles.tarjeta_enviada:
            sesion.historial = list(agente.messages)
            return self._fin_con_tarjeta(sesion)
        v = self._validar(texto, sesion)
        trace.get_current_span().add_event("validador", {"ok": v.ok, "motivo": v.motivo or ""})
        sesion.paso("Validador", "aprobada" if v.ok else f"rechazada: {v.motivo}")
        if not v.ok:
            for _ in range(REINTENTOS):  # hasta tres intentos por turno (D40)
                if v.ok or sesion.cerrada:
                    break
                texto, v = self._corregir(agente, controles, sesion, f"{v.motivo} Reescríbela.")
                sesion.paso("Reintento", "aprobado" if v.ok else f"rechazado: {v.motivo}")
            if not v.ok and agente.messages and agente.messages[-1]["role"] == "assistant":
                # Lo que el cliente recibe es el texto seguro: así queda en el historial y los
                # roles siguen alternándose (Bedrock Converse lo exige).
                agente.messages[-1] = {
                    "role": "assistant",
                    "content": [{"text": TEXTOS["respuesta_segura"]}],
                }
        elif _pide_confirmacion(texto) and not sesion.cerrada:
            # Un aviso, no un bloqueo: si la corrección no sirve, se envía la respuesta original.
            trace.get_current_span().add_event("confirma_en_texto")
            sesion.paso("Confirmación en texto", "se le pide usar la tarjeta")
            original, historial = texto, list(agente.messages)
            texto, v = self._corregir(agente, controles, sesion, _USA_LA_TARJETA)
            sesion.paso("Reintento", "aprobado" if v.ok else "rechazado: se envía la original")
            if not v.ok:
                texto, v = original, Validacion(ok=True)
                agente.messages[:] = historial
        sesion.historial = list(agente.messages)
        if controles.tarjeta_enviada:
            return self._fin_con_tarjeta(sesion)
        return texto if v.ok else None

    @staticmethod
    def _validar(texto: str, sesion: Sesion) -> Validacion:
        if not texto:
            return Validacion(ok=False, motivo="La respuesta está vacía.")
        # Cuotas y días de las ofertas consultadas: "3 cuotas" sale si coincide con una (D40).
        condiciones = sesion.condiciones.values()
        numeros = {
            "cuota": frozenset(c.numero_cuotas for c in condiciones),
            "dia": frozenset(c.dias_prorroga for c in condiciones),
        }
        return validar_salida(texto, set(sesion.valores), sesion.max_caracteres, numeros)

    @staticmethod
    def _fin_con_tarjeta(sesion: Sesion) -> str | None:
        """ "" si la tarjeta es el mensaje del turno; None si una tool también cerró la sesión: la
        tarjeta se descarta y se usa el texto fijo del cierre."""
        if sesion.cerrada:
            sesion.tarjeta = None
            return None
        return ""

    def _corregir(
        self, agente: Agent, controles: Controles, sesion: Sesion, motivo: str
    ) -> tuple[str, Validacion]:
        """Un reintento con el motivo; el intento fallido y el aviso no quedan en el historial."""
        fallido = agente.messages[-1]
        sesion.contexto = []
        texto = str(agente(f"[sistema] Tu respuesta no se envió: {motivo}")).strip()
        i = next((i for i, m in enumerate(agente.messages) if m is fallido), None)
        if i is not None:
            del agente.messages[i : i + 2]
        if controles.tarjeta_enviada:  # lo decide _fin_con_tarjeta
            return "", Validacion(ok=True)
        return texto, self._validar(texto, sesion)

    def _agente(self, sesion: Sesion) -> tuple[Agent, Controles]:
        cliente = self.repo.cliente(sesion.customer_id)
        perfil = cargar_perfil(sesion.segmento)
        controles = Controles(self.repo, sesion, self.ahora)
        agente = Agent(
            model=self.modelos.agente,
            system_prompt=prompt_sistema(perfil, cliente, self.ahora()),
            tools=crear_tools(self.repo, sesion, self.ahora),
            hooks=[controles],
            messages=sesion.historial,
            conversation_manager=SlidingWindowConversationManager(window_size=20),
            callback_handler=None,
            trace_attributes={
                "session.id": sesion.conversacion_id,
                "agil.segmento": sesion.segmento.value,
            },
        )
        return agente, controles

    # --- Lo que resuelve el código ---

    def _refrescar_cifras(self, sesion: Sesion) -> None:
        """Recalcula las cifras ya mostradas al llegar cada mensaje: entre mensajes una carga pudo
        aplicar un pago (H3). La oferta ya aceptada no cambia: es un acuerdo registrado. Una tarjeta
        pendiente cuyo monto cambió se anula."""
        if not sesion.valores:
            return
        cid = sesion.customer_id
        e = estado_cuenta(self.repo, cid)
        antes = dict(sesion.valores)
        if "saldo_vencido" in sesion.valores:
            sesion.valores.update(cifras_saldo(self.repo, e))
        aceptada = sesion.oferta_aceptada and sesion.oferta_aceptada.oferta_id
        abiertas = [oid for oid in sesion.condiciones if oid != aceptada]
        elegibles = (
            {o.oferta_id: o for o in ofertas_elegibles(self.repo, cid, sesion.segmento, e)}
            if abiertas
            else {}
        )
        retiradas = []
        for oferta_id in abiertas:
            o = elegibles.get(oferta_id)
            nuevas = o and condiciones(self.repo, cid, o, e)
            if nuevas == sesion.condiciones[oferta_id]:
                continue
            p = f"{prefijo(oferta_id)}."
            sesion.valores = {k: v for k, v in sesion.valores.items() if not k.startswith(p)}
            if nuevas:
                sesion.condiciones[oferta_id] = nuevas
                sesion.valores.update(cifras_oferta(nuevas))
            else:
                del sesion.condiciones[oferta_id]
                retiradas.append(oferta_id)
        if sesion.valores == antes:
            return
        evento = "[sistema] La cuenta del cliente cambió (p. ej. se aplicó un pago): cifras al día."
        if retiradas:
            sesion.valores.pop("opciones", None)  # el conteo ya no vale: que vuelva a consultar
            evento += f" Ya no aplican: {', '.join(retiradas)}."
        tarjeta = sesion.tarjeta
        if tarjeta and tarjeta.monto != self._monto_actual(sesion, tarjeta.oferta_id, e):
            sesion.tarjeta = None
            evento += f" Se anuló la tarjeta pendiente ({tarjeta.descripcion})."
        trace.get_current_span().add_event(
            "cifras_actualizadas",
            {
                "retiradas": len(retiradas),
                "tarjeta_anulada": tarjeta is not None and sesion.tarjeta is None,
            },
        )
        sesion.eventos.append(evento)

    @staticmethod
    def _monto_actual(sesion: Sesion, oferta_id: str | None, e: EstadoCuenta) -> Decimal | None:
        """Lo que hoy respalda una tarjeta: su oferta, la aceptada o el saldo (monto_a_cobrar)."""
        if oferta_id:
            c = sesion.condiciones.get(oferta_id)
            return c and c.primer_pago
        if sesion.oferta_aceptada:
            return sesion.oferta_aceptada.primer_pago
        return e.saldo_tras_transito

    def _verificar(self, sesion: Sesion, digitos: str) -> Respuesta | None:
        """El número nunca llega al LLM; solo el resultado (D24). Un intento fallido recibe un texto
        fijo y el tercero pasa a un asesor (D40); None si es correcta y sigue el agente."""
        cliente = self.repo.cliente(sesion.customer_id)
        if verificar(cliente, digitos):
            sesion.paso("Verificación de cédula", "correcta")
            sesion.verificada = True
            sesion.verificada_en = self.ahora()
            sesion.cedula_pedida = False
            sesion.intentos_cedula = 0  # si vence a las 12 h, vuelve a tener tres intentos
            sesion.recien_verificada = True
            evento = (  # sin citar sus mensajes: ya están en el historial (D43)
                "[sistema] Verificación de cédula correcta. Antes de responder, relee lo que pidió "
                "el cliente antes de verificar, incluido el mensaje que sigue a este aviso: si "
                "pidió algo que dejaste pendiente por no estar verificado, atiéndelo ahora (con la "
                "tool que corresponda si ya eligió una opción), sin saludar de nuevo. Lo que ya le "
                "respondiste no lo repitas."
            )
            notas = self.repo.notas(sesion.customer_id)[-3:]
            if notas:
                evento += " Notas de conversaciones anteriores: " + " | ".join(
                    n.texto for n in notas
                )
            sesion.eventos.append(evento)
            return None
        sesion.intentos_cedula += 1
        sesion.paso(
            "Verificación de cédula",
            f"fallida (intento {sesion.intentos_cedula} de {MAX_INTENTOS_CEDULA}); texto fijo",
        )
        bloqueada = sesion.intentos_cedula >= MAX_INTENTOS_CEDULA
        trace.get_current_span().add_event(
            "verificacion",
            {"resultado": "fallida", "intento": sesion.intentos_cedula, "bloqueada": bloqueada},
        )
        if bloqueada:
            sesion.cedula_pedida = False
            self._handoff(
                sesion,
                "cedula",
                "verificacion_fallida",
                "Tres intentos fallidos de los últimos cuatro dígitos de la cédula.",
            )
            return self._cierre_fijo(sesion, "handoff", TEXTOS["cedula_bloqueada"])
        sesion.eventos.append(
            f"[sistema] Verificación fallida (intento {sesion.intentos_cedula} de "
            f"{MAX_INTENTOS_CEDULA}); el sistema ya pidió revisarlos."
        )
        sesion.transcripcion.append(("agente", TEXTOS["cedula_no_coincide"]))
        return Respuesta(mensajes=[TEXTOS["cedula_no_coincide"]])

    def _boton(self, sesion: Sesion, boton: Boton) -> Respuesta:
        tarjeta = sesion.tarjeta
        sesion.tarjeta = None
        if tarjeta is None:
            sesion.paso("Botón", f"{boton.name} sin tarjeta vigente")
            return Respuesta(mensajes=[TEXTOS["sin_tarjeta"]])
        que = tarjeta.descripcion
        sesion.paso("Botón", f"{boton.name}: {que}")
        sesion.transcripcion.append(("cliente", f"[botón {boton.name}: {que}]"))
        if boton is Boton.cancelar:
            evento = f"[sistema] El cliente canceló la tarjeta ({que})."
            if tarjeta.tipo == "oferta":
                sesion.rechazadas.append(tarjeta.oferta_id)
                quedan = [
                    o.oferta_id
                    for o in escalera(self.repo, sesion)
                    if o.tipo != "cambio_fecha_corte"
                ]
                evento += (
                    f" Queda por ofrecer, en orden: {', '.join(quedan)}. No vuelvas al link de "
                    "pago inmediato ni a lo ya rechazado."
                    if quedan
                    else " No quedan opciones más generosas: dilo y ofrece un asesor."
                )
            sesion.eventos.append(evento)
            return self._turno_agente(sesion, f"Cliente: [tocó «{boton.name}»]")
        self._registrar(sesion, tarjeta)
        texto, url = self._confirmacion(sesion, tarjeta)
        trace.get_current_span().add_event("confirmacion_fija", {"tipo": tarjeta.tipo})
        sesion.paso("Registro", f"{que} registrada; respuesta fija" + (" con link" if url else ""))
        enviado = "la confirmación y el link de pago" if url else "la confirmación"
        sesion.eventos.append(
            f"[sistema] El cliente confirmó la tarjeta ({que}): registrada. El sistema ya le envió "
            f"{enviado}: no lo repitas."
        )
        # La transcripción alimenta el resumen de cierre: sin el link, que caduca.
        sesion.transcripcion.append(
            ("agente", texto.replace(url, "{{link_pago}}") if url else texto)
        )
        return Respuesta(mensajes=[texto])

    def _confirmacion(self, sesion: Sesion, tarjeta) -> tuple[str, str | None]:
        """Texto fijo tras Confirmar (D22): qué quedó registrado y, si falta pagar, el link."""
        nombre = self.repo.cliente(sesion.customer_id).nombre.split()[0]
        cierre = " ¿Le ayudo con algo más?"
        url, nuevo = None, False
        if tarjeta.monto > 0:
            url, nuevo = link_pago(self.repo, sesion, tarjeta.monto, self.ahora)
        dinero = formato.dinero(tarjeta.monto)
        if tarjeta.tipo == "promesa":
            link = f"este link: {url}." if nuevo else "el link que le envié."
            return (
                f"Listo, {nombre}. Quedó registrada su promesa de pago de {dinero} para el "
                f"{formato.fecha(tarjeta.fecha)}. Ese día puede pagar con {link}{cierre}"
            ), url if nuevo else None
        c = sesion.oferta_aceptada
        oferta = next(o for o in self.repo.ofertas() if o.oferta_id == tarjeta.oferta_id)
        if oferta.tipo == "cambio_fecha_corte":
            texto = f"Listo, {nombre}. Quedó aceptado el cambio de fecha de corte."
            pago = f" Su saldo vencido sigue pendiente: puede pagar {dinero}"
        else:
            texto = f"Listo, {nombre}. Quedó aceptada su oferta."
            pago = f" Puede pagar {'la primera cuota, ' if c.numero_cuotas else ''}{dinero}"
            if c.fecha_limite:
                pago += f", hasta el {formato.fecha(c.fecha_limite)}"
        if url:
            texto += f"{pago}, con este link: {url}."
        return texto + cierre, url

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
            sesion.acuerdos.append(f"oferta {tarjeta.oferta_id} aceptada")
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
            # La fecha va escrita: el agente puede leer cifras, no escribirlas, y un placeholder
            # compartido lo pisaría la siguiente tarjeta.
            sesion.acuerdos.append(f"promesa de pago para el {formato.fecha(tarjeta.fecha)}")
        sesion.escrituras.add(sufijo)

    def _no_contactar(self, sesion: Sesion, texto: str) -> Respuesta:
        """Frase explícita (D13): se deriva y pausa sin LLM; el evento llega al resumen."""
        sesion.paso("No contactar", "frase explícita: solicitud registrada y WhatsApp pausado")
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

    def _pide_humano(self, sesion: Sesion) -> Respuesta | None:
        """Cuenta los pedidos de un asesor; al segundo, handoff con texto fijo (D45)."""
        sesion.pedidos_humano += 1
        sesion.paso("Pide un asesor", f"pedido {sesion.pedidos_humano} de {MAX_PEDIDOS_HUMANO}")
        handoff = sesion.pedidos_humano >= MAX_PEDIDOS_HUMANO
        trace.get_current_span().add_event(
            "pide_humano", {"pedido": sesion.pedidos_humano, "handoff": handoff}
        )
        if not handoff:
            return None
        self._handoff(
            sesion, "humano", "pide_humano", "El cliente pidió un asesor por segunda vez."
        )
        return self._cierre_fijo(sesion, "handoff", TEXTOS["handoff"])

    def _sin_sentido(self, sesion: Sesion) -> Respuesta:
        sesion.sin_sentido += 1
        trace.get_current_span().add_event("sin_sentido", {"seguidos": sesion.sin_sentido})
        sesion.paso("Sin sentido", f"texto fijo, sin LLM ({sesion.sin_sentido} de {MAX_STRIKES})")
        if sesion.sin_sentido >= MAX_STRIKES:
            return self._cierre_fijo(sesion, "sin_sentido", TEXTOS["sin_sentido_cierre"])
        sesion.transcripcion.append(("agente", TEXTOS["sin_sentido"]))
        return Respuesta(mensajes=[TEXTOS["sin_sentido"]])

    def _abuso(self, sesion: Sesion) -> Respuesta:
        sesion.strikes += 1
        sesion.paso("Respuesta fija", f"mensaje abusivo: strike {sesion.strikes} de {MAX_STRIKES}")
        if sesion.strikes >= MAX_STRIKES:
            return self._cierre_fijo(sesion, "abuso", TEXTOS["abuso_cierre"])
        sesion.eventos.append(
            f"[sistema] Mensaje abusivo del cliente (strike {sesion.strikes} de {MAX_STRIKES}); "
            "se respondió con el texto fijo."
        )
        sesion.transcripcion.append(("agente", TEXTOS["abuso"]))
        return Respuesta(mensajes=[TEXTOS["abuso"]])

    def _handoff(self, sesion: Sesion, sufijo: str, motivo: str, resumen: str) -> None:
        self.repo.guardar_handoff(
            Handoff(
                handoff_id=f"HO-{sesion.conversacion_id}-{sufijo}",
                customer_id=sesion.customer_id,
                cola=sesion.cola,
                motivo=motivo,
                resumen=resumen,
                creado=self.ahora(),
            )
        )

    def _cierre_fijo(self, sesion: Sesion, motivo: str, texto: str) -> Respuesta:
        sesion.paso("Cierre", f"{motivo}; texto fijo")
        sesion.transcripcion.append(("agente", texto))
        self.cerrar(sesion, motivo)
        return Respuesta(mensajes=[texto], cerrada=True)
