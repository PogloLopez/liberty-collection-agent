"""Motor de reglas de ofertas (D3). Una oferta fuera de la tabla no existe."""

from decimal import Decimal

from agil.dominio.calculos import estado_cuenta, saldo_factura
from agil.dominio.datos import Repositorio
from agil.dominio.modelos import EstadoCuenta, Oferta, Segmento, Validacion

_CERO = Decimal("0.00")


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
    repo: Repositorio, customer_id: str, segmento: Segmento, oferta: Oferta
) -> str | None:
    oid = oferta.oferta_id
    if not oferta.vigencia_desde <= repo.fecha_referencia <= oferta.vigencia_hasta:
        return f"La oferta {oid} no está vigente. No la menciones."
    if segmento not in oferta.segmentos_elegibles:
        return f"La oferta {oid} no aplica al segmento de este cliente."
    estado = estado_cuenta(repo, customer_id)
    if estado.saldo_vencido <= 0:
        return "El cliente no tiene saldo vencido: ninguna oferta aplica."
    if estado.saldo_tras_transito <= 0:
        return "El pago en tránsito del cliente ya cubre su saldo: ninguna oferta aplica."
    monto = _monto_base(repo, customer_id, oferta, estado)
    if monto is None:
        return f"La oferta {oid} no aplica: el cliente no tiene cargos sobre los que aplicarla."
    if oferta.aplica_a != "cuenta" and not oferta.monto_min <= monto <= oferta.monto_max:
        return f"La oferta {oid} no aplica: el monto del cliente está fuera de su rango."
    return None


def ofertas_elegibles(repo: Repositorio, customer_id: str, segmento: Segmento) -> list[Oferta]:
    """Segmento elegible, vigente y monto base (según `aplica_a`) en [monto_min, monto_max].

    `segmento` lo inyecta la sesión desde `segmentar`, nunca el LLM. Incluye las que requieren
    aprobación humana: `validar_oferta` las rechaza para escalar.
    """
    if repo.cliente(customer_id) is None:
        return []
    return [o for o in repo.ofertas() if _motivo_rechazo(repo, customer_id, segmento, o) is None]


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
    if repo.cliente(customer_id) is None:
        return Validacion(ok=False, motivo="Cliente desconocido.")
    motivo = _motivo_rechazo(repo, customer_id, segmento, oferta)
    if motivo is None and oferta.requiere_aprobacion_humana:
        motivo = (
            f"La oferta {oferta_id} requiere aprobación humana: no la aceptes, "
            "escala a un asesor con escalar_a_humano."
        )
    return Validacion(ok=motivo is None, motivo=motivo)
