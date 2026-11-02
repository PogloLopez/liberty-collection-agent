"""Las 10 tools del agente (tools.md). El `customer_id` y el segmento salen de la sesión: ninguna
tool los recibe del LLM. Las cifras vuelven junto al placeholder que el LLM debe escribir (D28)."""

import hashlib
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from strands import tool

from agil.agente import formato
from agil.agente.sesion import Sesion, Tarjeta
from agil.dominio.modelos import (
    Cola,
    CondicionesOferta,
    EstadoCuenta,
    EtiquetaFeedback,
    Feedback,
    FlagMemoria,
    Handoff,
    LinkPago,
    Nota,
    Oferta,
    SolicitudNoContacto,
)
from agil.dominio.reglas.calculos import estado_cuenta
from agil.dominio.reglas.calendario import resolver_dia
from agil.dominio.reglas.ofertas import condiciones, ofertas_elegibles, validar_fecha_promesa
from agil.dominio.repositorio.interfaz import Repositorio

# Exigen la verificación de cédula (D5); un hook las cancela antes.
SENSIBLES = frozenset(
    {
        "consultar_saldo",
        "consultar_ofertas_elegibles",
        "aceptar_oferta",
        "registrar_promesa_pago",
        "generar_link_pago",
        "guardar_nota",
        "registrar_feedback_cliente",
        "solicitar_cambio_fecha_corte",
    }
)
URL_PAGOS = "https://pagos.liberty.example/l/"
_ESCRIBE = "Escribe los placeholders tal cual; nunca las cifras."
_TARJETA = "Tarjeta enviada: el cliente la confirma con los botones. El turno termina aquí."
CONFIRMA_OFERTA = "Toque Confirmar para aceptarla o Cancelar para ver otras opciones."
CONFIRMA_PROMESA = "Toque Confirmar para registrarla o Cancelar para elegir otra fecha."


class MotivoEscalamiento(StrEnum):
    pide_humano = "pide_humano"
    fuera_de_tabla = "fuera_de_tabla"  # pide algo que no está en las ofertas (D3)
    disputa = "disputa"
    vulnerable = "vulnerable"
    otro = "otro"


def prefijo(oferta_id: str) -> str:
    """'OF-104' → 'of_104' (placeholders con prefijo de oferta, D28)."""
    return oferta_id.lower().replace("-", "_")


def cifras_oferta(c: CondicionesOferta) -> dict[str, str]:
    """Nombre del placeholder (sin llaves) → cifra formateada; solo los campos que aplican."""
    campos = {
        "monto_a_pagar": formato.dinero(c.monto_a_pagar),
        "porcentaje_descuento": c.porcentaje_descuento
        and formato.porcentaje(c.porcentaje_descuento),
        "monto_descuento": c.monto_descuento and formato.dinero(c.monto_descuento),
        "numero_cuotas": c.numero_cuotas and str(c.numero_cuotas),
        "monto_cuota": c.monto_cuota and formato.dinero(c.monto_cuota),
        # Si la última es igual a las demás no se entrega: "y la última de…" confunde (D40).
        "monto_ultima_cuota": c.monto_ultima_cuota != c.monto_cuota
        and c.monto_ultima_cuota
        and formato.dinero(c.monto_ultima_cuota),
        "dias_prorroga": c.dias_prorroga and str(c.dias_prorroga),
        "fecha_limite": c.fecha_limite and formato.fecha(c.fecha_limite),
    }
    p = prefijo(c.oferta_id)
    return {f"{p}.{k}": v for k, v in campos.items() if v}


def texto_tarjeta_oferta(oferta: Oferta, c: CondicionesOferta) -> str:
    partes = [f"{oferta.nombre}."]
    if c.monto_descuento and oferta.aplica_a != "cargo_mensual":
        partes.append(f"Descuento de {formato.dinero(c.monto_descuento)}.")
    elif c.porcentaje_descuento:
        partes.append(
            f"Descuento de {formato.porcentaje(c.porcentaje_descuento)} en su cargo mensual."
        )
    if c.numero_cuotas and c.monto_cuota:
        cuota, ultima = formato.dinero(c.monto_cuota), formato.dinero(c.monto_ultima_cuota)
        if c.monto_ultima_cuota == c.monto_cuota:
            partes.append(f"Paga {c.numero_cuotas} cuotas de {cuota}.")
        else:
            partes.append(f"Paga {c.numero_cuotas} cuotas: de {cuota} y la última de {ultima}.")
    elif c.monto_a_pagar > 0 and oferta.tipo != "cambio_fecha_corte":
        partes.append(f"Total a pagar: {formato.dinero(c.monto_a_pagar)}.")
    if c.fecha_limite:
        partes.append(f"Fecha límite: {formato.fecha(c.fecha_limite)}.")
    partes.append(CONFIRMA_OFERTA)
    return " ".join(partes)


def cifras_saldo(repo: Repositorio, e: EstadoCuenta) -> dict[str, str]:
    """Placeholders de consultar_saldo (sin llaves) → cifra formateada."""
    valores = {
        "saldo_vencido": formato.dinero(e.saldo_vencido),
        "dias_mora": str(e.dias_mora),
        "monto_en_transito": formato.dinero(e.monto_en_transito),
        "saldo_tras_transito": formato.dinero(e.saldo_tras_transito),
        "plazo_aplicacion": repo.parametros["plazo_aplicacion_pago"],
    }
    if e.facturas_vencidas:
        antigua = min(e.facturas_vencidas, key=lambda f: f.fecha_vencimiento)
        valores["periodo_factura"] = formato.periodo(antigua.periodo)
        valores["fecha_vencimiento"] = formato.fecha(antigua.fecha_vencimiento)
    return valores


def _generosidad(o: Oferta) -> tuple:
    """De menos a más generosa (D28): el agente sube un escalón a la vez."""
    p = o.parametros
    return (p.porcentaje_descuento or 0, p.numero_cuotas or 0, o.requiere_aprobacion_humana)


def _con_llaves(valores: dict[str, str]) -> dict[str, str]:
    return {f"{{{{{k}}}}}": v for k, v in valores.items()}


def id_de(sesion: Sesion, prefijo_id: str, *partes: object) -> str:
    """Determinista por conversación y argumentos: la misma escritura da el mismo ID."""
    clave = "|".join(str(p) for p in (sesion.conversacion_id, prefijo_id, *partes))
    return f"{prefijo_id}-{hashlib.sha1(clave.encode()).hexdigest()[:10]}"


def link_pago(
    repo: Repositorio, sesion: Sesion, monto: Decimal, ahora: Callable[[], datetime]
) -> tuple[str, bool]:
    """URL del link por `monto` y si es nuevo en la conversación (el mismo monto, el mismo link)."""
    link_id = id_de(sesion, "LK", monto)
    url = URL_PAGOS + link_id
    nuevo = link_id not in sesion.escrituras
    if nuevo:
        repo.guardar_link(
            LinkPago(
                link_id=link_id,
                customer_id=sesion.customer_id,
                monto=monto,
                url=url,
                creado=ahora(),
            )
        )
        sesion.escrituras.add(link_id)
    sesion.valores.update({"link_pago": url, "monto_link": formato.dinero(monto)})
    return url, nuevo


def crear_tools(repo: Repositorio, sesion: Sesion, ahora: Callable[[], datetime]) -> list:
    cid = sesion.customer_id

    def nuevo_id(prefijo_id: str, *partes: object) -> str | None:
        """None si ya se escribió (idempotencia). Se marca como escrito tras guardar."""
        id_ = id_de(sesion, prefijo_id, *partes)
        return None if id_ in sesion.escrituras else id_

    def oferta(
        oferta_id: str, estado: EstadoCuenta | None = None
    ) -> tuple[Oferta, CondicionesOferta]:
        o = next((o for o in repo.ofertas() if o.oferta_id == oferta_id), None)
        if o is None:  # el hook ya lo impide; respaldo
            raise ValueError(f"La oferta {oferta_id} no existe.")
        c = sesion.condiciones.get(oferta_id) or condiciones(repo, cid, o, estado)
        sesion.condiciones[oferta_id] = c
        sesion.valores.update(cifras_oferta(c))
        return o, c

    def monto_a_cobrar():
        if sesion.oferta_aceptada:
            return sesion.oferta_aceptada.primer_pago
        return estado_cuenta(repo, cid).saldo_tras_transito

    @tool
    def consultar_saldo() -> dict:
        """Saldo vencido, días de mora, factura más antigua y pagos en tránsito del cliente."""
        e = estado_cuenta(repo, cid)
        valores = cifras_saldo(repo, e)
        sesion.valores.update(valores)
        return {
            "cifras": _con_llaves(valores),
            "facturas_vencidas": len(e.facturas_vencidas),
            "pagos_en_transito": len(e.pagos_en_transito),
            "instruccion": _ESCRIBE,
        }

    @tool
    def consultar_ofertas_elegibles() -> dict:
        """Ofertas preaprobadas para este cliente, de la menos a la más generosa, con sus cifras."""
        resultado = []
        e = estado_cuenta(repo, cid)
        for o in sorted(ofertas_elegibles(repo, cid, sesion.segmento, e), key=_generosidad):
            _, c = oferta(o.oferta_id, e)
            resultado.append(
                {
                    "oferta_id": o.oferta_id,
                    "nombre": o.nombre,
                    "tipo": o.tipo,
                    "requiere_aprobacion_humana": o.requiere_aprobacion_humana,
                    "cifras": _con_llaves(cifras_oferta(c)),
                }
            )
        return {"ofertas": resultado, "instruccion": _ESCRIBE}

    @tool
    def aceptar_oferta(oferta_id: str) -> str:
        """Envía al cliente una tarjeta con botones para confirmar la oferta: la tarjeta es la
        pregunta y el sistema la registra solo si confirma. Úsala apenas el cliente elija una."""
        o, c = oferta(oferta_id)
        sesion.tarjeta = Tarjeta(
            tipo="oferta",
            texto=texto_tarjeta_oferta(o, c),
            monto=c.primer_pago,
            oferta_id=oferta_id,
        )
        return _TARJETA

    @tool
    def registrar_promesa_pago(fecha: str, oferta_id: str | None = None) -> str:
        """Envía una tarjeta con botones para confirmar una promesa de pago; úsala apenas el cliente
        diga el día.

        Args:
            fecha: el día tal como lo dijo el cliente ("el miércoles", "mañana", "el 15",
                "dentro de 10 días"); nunca lo conviertas tú.
            oferta_id: la oferta de la promesa, si la hay; si no, se promete el saldo.
        """
        dia = resolver_dia(fecha, repo.fecha_referencia)
        if dia is None:
            return (
                "No entendí la fecha. No la calcules tú: pide al cliente un día concreto (un día "
                "de la semana, 'mañana', 'dentro de N días' o día y mes) y pásalo tal como lo diga."
            )
        v = validar_fecha_promesa(repo, cid, sesion.segmento, dia)
        if not v.ok:
            return v.motivo
        c = oferta(oferta_id)[1] if oferta_id else None
        if c and c.fecha_limite and dia > c.fecha_limite:
            return f"Con la oferta {oferta_id} la fecha no puede pasar de su fecha límite."
        monto = c.primer_pago if c else monto_a_cobrar()
        if monto <= 0:
            return "No hay saldo por prometer (o un pago en tránsito lo cubre)."
        sesion.valores["fecha_promesa"] = formato.fecha(dia)
        sesion.tarjeta = Tarjeta(
            tipo="promesa",
            texto=f"Promesa de pago de {formato.dinero(monto)} para el {formato.fecha(dia)}. "
            + CONFIRMA_PROMESA,
            monto=monto,
            oferta_id=oferta_id,
            fecha=dia,
        )
        return _TARJETA

    @tool
    def generar_link_pago() -> dict:
        """Link de pago por la oferta aceptada (primera cuota o total) o, si no hay, el saldo."""
        monto = monto_a_cobrar()
        if monto <= 0:
            return {"error": "No hay saldo por cobrar (o un pago en tránsito lo cubre)."}
        link_pago(repo, sesion, monto, ahora)
        valores = {k: sesion.valores[k] for k in ("link_pago", "monto_link")}
        return {"cifras": _con_llaves(valores), "instruccion": _ESCRIBE}

    @tool
    def guardar_nota(texto: str, flags: list[FlagMemoria]) -> str:
        """Nota para la próxima conversación: texto libre y flags del catálogo (o ninguno)."""
        if nota_id := nuevo_id("NT", texto, sorted(flags)):
            repo.guardar_nota(
                Nota(
                    nota_id=nota_id,
                    customer_id=cid,
                    fecha=ahora(),
                    origen="agente",
                    conversacion_id=sesion.conversacion_id,
                    texto=texto,
                    flags=flags,
                )
            )
            sesion.escrituras.add(nota_id)
        return "Nota guardada."

    @tool
    def registrar_feedback_cliente(texto: str, etiquetas: list[EtiquetaFeedback]) -> str:
        """Feedback del cliente sobre el negocio (servicio, precio, facturación, medio de pago)."""
        if feedback_id := nuevo_id("FB", texto, sorted(etiquetas)):
            repo.guardar_feedback(
                Feedback(
                    feedback_id=feedback_id,
                    customer_id=cid,
                    texto=texto,
                    etiquetas=etiquetas,
                    creado=ahora(),
                )
            )
            sesion.escrituras.add(feedback_id)
        return "Feedback registrado."

    @tool
    def derivar_solicitud_contacto(texto: str) -> str:
        """El cliente pide no ser contactado: registra la solicitud, pausa WhatsApp y cierra la
        conversación. La deuda sigue vigente por otros canales; no prometas darla de baja.

        Args:
            texto: lo que pidió el cliente, en sus palabras.
        """
        if solicitud_id := nuevo_id("NC"):
            repo.guardar_solicitud_no_contacto(
                SolicitudNoContacto(
                    solicitud_id=solicitud_id, customer_id=cid, texto=texto, creada=ahora()
                )
            )
            repo.pausar_whatsapp(cid, ahora().date())
            sesion.escrituras.add(solicitud_id)
        sesion.cerrar("no_contactar")
        return "Solicitud registrada y conversación cerrada. Despídete en una frase."

    @tool
    def solicitar_cambio_fecha_corte(texto: str) -> str:
        """El cliente quiere que su factura venza otro día de cada mes y la oferta de cambio de
        fecha de corte no está entre sus ofertas: registra la solicitud para un asesor (cola básica)
        sin cerrar la conversación.

        Args:
            texto: lo que pidió el cliente, con el día que quiere, sin datos de la cédula.
        """
        if handoff_id := nuevo_id("HO", "corte", texto):
            repo.guardar_handoff(
                Handoff(
                    handoff_id=handoff_id,
                    customer_id=cid,
                    cola=Cola.basica,
                    motivo="cambio_fecha_corte",
                    resumen=texto,
                    creado=ahora(),
                )
            )
            sesion.escrituras.add(handoff_id)
        return (
            "Solicitud registrada: un asesor gestionará el cambio. Díselo al cliente sin prometer "
            "tiempos y sigue con la deuda vencida: el cambio no la resuelve."
        )

    @tool
    def escalar_a_humano(motivo: MotivoEscalamiento, resumen: str) -> str:
        """Pasa la conversación a un asesor y la cierra. Úsala si el cliente pide un humano después
        de tu primer intento, si pide algo fuera de las ofertas (salvo el cambio de fecha de corte:
        solicitar_cambio_fecha_corte) o ante una disputa o vulnerabilidad.

        Args:
            motivo: por qué se escala.
            resumen: dos o tres frases para el asesor, sin datos de la cédula.
        """
        motivo = MotivoEscalamiento(motivo)
        cola = {
            MotivoEscalamiento.disputa: Cola.reclamos,
            MotivoEscalamiento.vulnerable: Cola.especializada,
        }.get(motivo, sesion.cola)
        if handoff_id := nuevo_id("HO"):
            repo.guardar_handoff(
                Handoff(
                    handoff_id=handoff_id,
                    customer_id=cid,
                    cola=cola,
                    motivo=motivo.value,
                    resumen=resumen,
                    creado=ahora(),
                )
            )
            sesion.escrituras.add(handoff_id)
        sesion.cerrar("handoff")
        return "Un asesor tomará la conversación. Despídete en una frase, sin prometer tiempos."

    return [
        consultar_saldo,
        consultar_ofertas_elegibles,
        aceptar_oferta,
        registrar_promesa_pago,
        generar_link_pago,
        guardar_nota,
        registrar_feedback_cliente,
        derivar_solicitud_contacto,
        solicitar_cambio_fecha_corte,
        escalar_a_humano,
    ]
