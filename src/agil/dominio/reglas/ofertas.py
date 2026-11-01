"""Motor de reglas de ofertas (D3). Una oferta fuera de la tabla no existe."""

from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from agil.dominio.modelos import CondicionesOferta, EstadoCuenta, Oferta, Segmento, Validacion
from agil.dominio.reglas.calculos import estado_cuenta, saldo_factura
from agil.dominio.repositorio.interfaz import Repositorio

_CERO = Decimal("0.00")
_CENTAVO = Decimal("0.01")


def _monto_base(
    repo: Repositorio, customer_id: str, oferta: Oferta, estado: EstadoCuenta
) -> Decimal | None:
    """Monto sobre el que actúa la oferta según `aplica_a`; None si no hay sobre qué aplicarla."""
    match oferta.aplica_a:
        case "saldo_vencido" | "cuenta":
            return estado.saldo_vencido
        case "factura_vencida":
            if not estado.facturas_vencidas:
                return None
            return saldo_factura(estado.facturas_vencidas[0], repo.pagos(customer_id))
        case "cargo_mensual":
            return repo.cliente(customer_id).arpu_usd
        case "cargo_reconexion":
            total = sum(
                (
                    c.monto
                    for f in estado.facturas_vencidas
                    for c in f.detalle
                    if "reconexi" in c.concepto.lower()
                ),
                _CERO,
            )
            return total if total > 0 else None
    return None


def _motivo_rechazo(
    repo: Repositorio, customer_id: str, segmento: Segmento, oferta: Oferta, estado: EstadoCuenta
) -> str | None:
    oid = oferta.oferta_id
    if not oferta.vigencia_desde <= repo.fecha_referencia <= oferta.vigencia_hasta:
        return f"La oferta {oid} no está vigente. No la menciones."
    if segmento not in oferta.segmentos_elegibles:
        return f"La oferta {oid} no aplica al segmento de este cliente."
    if estado.saldo_tras_transito <= 0:
        return "El cliente no tiene saldo pendiente (o un pago en tránsito lo cubre): no aplica."
    monto = _monto_base(repo, customer_id, oferta, estado)
    if monto is None:
        return f"La oferta {oid} no aplica: el cliente no tiene cargos sobre los que aplicarla."
    if oferta.aplica_a != "cuenta" and not oferta.monto_min <= monto <= oferta.monto_max:
        return f"La oferta {oid} no aplica: el monto del cliente está fuera de su rango."
    return None


def ofertas_elegibles(repo: Repositorio, customer_id: str, segmento: Segmento) -> list[Oferta]:
    """Segmento elegible, vigente y monto base (según `aplica_a`) en [monto_min, monto_max].

    `segmento` lo inyecta la sesión desde `segmentar`, nunca el LLM. Incluye las que requieren
    aprobación humana: `validar_oferta` las rechaza para escalar. KeyError si el cliente no existe.
    """
    estado = estado_cuenta(repo, customer_id)
    return [
        o for o in repo.ofertas() if _motivo_rechazo(repo, customer_id, segmento, o, estado) is None
    ]


def validar_oferta(
    repo: Repositorio, customer_id: str, segmento: Segmento, oferta_id: str
) -> Validacion:
    """Motivo explicable al LLM si no existe, venció, no aplica o requiere aprobación humana."""
    oferta = next((o for o in repo.ofertas() if o.oferta_id == oferta_id), None)
    if oferta is None:
        return Validacion(
            ok=False,
            motivo=f"La oferta {oferta_id} no existe. Usa solo IDs de consultar_ofertas_elegibles.",
        )
    motivo = _motivo_rechazo(repo, customer_id, segmento, oferta, estado_cuenta(repo, customer_id))
    if motivo is None and oferta.requiere_aprobacion_humana:
        motivo = (
            f"La oferta {oferta_id} requiere aprobación humana: no la aceptes, "
            "escala a un asesor con escalar_a_humano."
        )
    return Validacion(ok=motivo is None, motivo=motivo)


def _redondear(monto: Decimal, modo: str = ROUND_HALF_UP) -> Decimal:
    return monto.quantize(_CENTAVO, rounding=modo)


def condiciones(repo: Repositorio, customer_id: str, oferta: Oferta) -> CondicionesOferta:
    """Cifras que el código calcula para la oferta (D28). Llamar solo con ofertas elegibles.

    El descuento se calcula sobre lo que queda por pagar (nunca más que el saldo tras los pagos en
    tránsito) y se resta de él, salvo el del cargo mensual, que aplica a las facturas futuras. Las
    cuotas se redondean hacia abajo y la última absorbe los centavos: suman exacto.
    """
    estado = estado_cuenta(repo, customer_id)
    base = _monto_base(repo, customer_id, oferta, estado)
    if base is None:
        raise ValueError(f"La oferta {oferta.oferta_id} no aplica a {customer_id}")
    par = oferta.parametros
    saldo = estado.saldo_tras_transito
    descuento = None
    a_pagar = saldo
    if par.porcentaje_descuento is not None:
        if oferta.aplica_a == "cargo_mensual":
            descuento = _redondear(base * par.porcentaje_descuento / 100)
        else:
            descuento = _redondear(min(base, saldo) * par.porcentaje_descuento / 100)
            a_pagar = saldo - descuento
    cuota = ultima = None
    if par.numero_cuotas:
        cuota = _redondear(a_pagar / par.numero_cuotas, ROUND_DOWN)
        ultima = a_pagar - cuota * (par.numero_cuotas - 1)
    limite = None
    if par.dias_prorroga:
        limite = repo.fecha_referencia + timedelta(days=par.dias_prorroga)
    return CondicionesOferta(
        oferta_id=oferta.oferta_id,
        monto_base=base,
        monto_a_pagar=a_pagar,
        porcentaje_descuento=par.porcentaje_descuento,
        monto_descuento=descuento,
        numero_cuotas=par.numero_cuotas,
        monto_cuota=cuota,
        monto_ultima_cuota=ultima,
        dias_prorroga=par.dias_prorroga,
        fecha_limite=limite,
    )


def validar_fecha_promesa(
    repo: Repositorio, customer_id: str, segmento: Segmento, fecha: date
) -> Validacion:
    """Ventana de la promesa (D32): de mañana a hoy + la prórroga máxima de las elegibles."""
    maximo = max(
        (o.parametros.dias_prorroga or 0 for o in ofertas_elegibles(repo, customer_id, segmento)),
        default=0,
    )
    if not maximo:
        return Validacion(
            ok=False,
            motivo="Este cliente no tiene prórroga aprobada: ofrece el link de pago o sus ofertas.",
        )
    hoy = repo.fecha_referencia
    if not hoy < fecha <= hoy + timedelta(days=maximo):
        return Validacion(
            ok=False,
            motivo=f"La fecha queda fuera de la ventana: entre mañana y {maximo} días. "
            "Pide otra fecha al cliente.",
        )
    return Validacion(ok=True)
