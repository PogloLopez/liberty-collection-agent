"""Variables de segmentación, calculadas a `repo.fecha_referencia` (reglas en datos_mock.md)."""

from datetime import date, timedelta
from decimal import Decimal

from agil.dominio.calendario import ZONA
from agil.dominio.modelos import EstadoCuenta, EstadoScore, Factura, Pago, Variables
from agil.dominio.repositorio.interfaz import Repositorio

_VENCIDAS = ("vencida", "parcial")
_CERO = Decimal("0.00")


def _aplicados(pagos: list[Pago], factura_id: str) -> list[Pago]:
    return [p for p in pagos if p.factura_id == factura_id and p.estado == "aplicado"]


def saldo_factura(factura: Factura, pagos: list[Pago]) -> Decimal:
    """Monto menos pagos aplicados."""
    return factura.monto - sum((p.monto for p in _aplicados(pagos, factura.factura_id)), _CERO)


def estado_cuenta(repo: Repositorio, customer_id: str) -> EstadoCuenta:
    """Lo que devuelve `consultar_saldo`. Facturas en disputa no suman al saldo."""
    if repo.cliente(customer_id) is None:
        raise KeyError(customer_id)
    pagos = repo.pagos(customer_id)
    vencidas = sorted(
        (f for f in repo.facturas(customer_id) if f.estado in _VENCIDAS),
        key=lambda f: f.fecha_vencimiento,
    )
    saldo = sum((saldo_factura(f, pagos) for f in vencidas), _CERO)
    dias_mora = (repo.fecha_referencia - vencidas[0].fecha_vencimiento).days if vencidas else 0
    ids_vencidas = {f.factura_id for f in vencidas}
    en_transito = [p for p in pagos if p.estado == "en_transito" and p.factura_id in ids_vencidas]
    monto_transito = sum((p.monto for p in en_transito), _CERO)
    return EstadoCuenta(
        customer_id=customer_id,
        saldo_vencido=saldo,
        dias_mora=dias_mora,
        facturas_vencidas=vencidas,
        pagos_en_transito=en_transito,
        monto_en_transito=monto_transito,
        saldo_tras_transito=max(saldo - monto_transito, _CERO),
    )


def _fecha_pago_total(factura: Factura, pagos: list[Pago]) -> date | None:
    acumulado = _CERO
    for p in sorted(_aplicados(pagos, factura.factura_id), key=lambda p: p.fecha):
        acumulado += p.monto
        if acumulado >= factura.monto:
            return p.fecha.astimezone(ZONA).date()
    return None


def _moras_12m(repo: Repositorio, customer_id: str) -> int:
    pagos = repo.pagos(customer_id)
    ref = repo.fecha_referencia
    desde = ref - timedelta(days=365)
    moras = 0
    for f in repo.facturas(customer_id):
        if f.estado == "en_disputa" or not desde <= f.fecha_vencimiento < ref:
            continue
        pagada = _fecha_pago_total(f, pagos)
        if pagada is None or pagada > f.fecha_vencimiento:
            moras += 1
    return moras


def _meses_entre(inicio: date, fin: date) -> int:
    meses = (fin.year - inicio.year) * 12 + fin.month - inicio.month
    return meses - 1 if fin.day < inicio.day else meses


def estado_score(repo: Repositorio, customer_id: str) -> EstadoScore:
    score = repo.score(customer_id)
    if score is None:
        return EstadoScore.faltante
    edad = (repo.fecha_referencia - score.fecha_calculo).days
    vigente = edad <= repo.parametros["score_vigencia_dias"]
    return EstadoScore.vigente if vigente else EstadoScore.vencido


def variables(repo: Repositorio, customer_id: str) -> Variables:
    """dias_mora, saldo_vencido, moras_12m, monto_en_transito, antiguedad_meses, arpu,
    estado_score."""
    cliente = repo.cliente(customer_id)
    if cliente is None:
        raise KeyError(customer_id)
    cuenta = estado_cuenta(repo, customer_id)
    return Variables(
        dias_mora=cuenta.dias_mora,
        saldo_vencido=cuenta.saldo_vencido,
        moras_12m=_moras_12m(repo, customer_id),
        monto_en_transito=cuenta.monto_en_transito,
        antiguedad_meses=_meses_entre(cliente.fecha_alta, repo.fecha_referencia),
        arpu_usd=cliente.arpu_usd,
        estado_score=estado_score(repo, customer_id),
    )
