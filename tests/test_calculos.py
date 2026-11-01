"""Variables y estado de cuenta contra el oráculo y los casos borde de datos_mock.md."""

import json
from decimal import Decimal

import pytest

from agil.dominio.modelos import EstadoScore
from agil.dominio.reglas.calculos import estado_cuenta, variables
from agil.dominio.repositorio.memoria import DATOS_MOCK, RepositorioMemoria

ORACULO = json.loads((DATOS_MOCK / "etiquetas_esperadas.json").read_text(encoding="utf-8"))
REPO = RepositorioMemoria()


@pytest.mark.parametrize("esperado", ORACULO, ids=lambda e: e["customer_id"])
def test_variables_coinciden_con_oraculo(esperado):
    obtenidas = variables(REPO, esperado["customer_id"]).model_dump(mode="json")
    assert obtenidas == esperado["variables"]


def test_montos_son_decimal():
    v = variables(REPO, "CL-1140215")
    assert isinstance(v.saldo_vencido, Decimal)
    assert isinstance(v.monto_en_transito, Decimal)


@pytest.mark.parametrize(
    ("customer_id", "dias"),
    [("CL-1197204", 15), ("CL-1203027", 16), ("CL-1168863", 60), ("CL-1183069", 61)],
)
def test_dias_mora_de_borde(customer_id, dias):
    assert variables(REPO, customer_id).dias_mora == dias


@pytest.mark.parametrize(("customer_id", "moras"), [("CL-1165562", 3), ("CL-1181514", 2)])
def test_moras_de_borde(customer_id, moras):
    assert variables(REPO, customer_id).moras_12m == moras


@pytest.mark.parametrize(
    ("customer_id", "estado"),
    [
        ("CL-1178922", EstadoScore.vigente),
        ("CL-1215806", EstadoScore.vencido),
        ("CL-1107377", EstadoScore.vencido),
        ("CL-1195028", EstadoScore.faltante),
    ],
)
def test_estado_score(customer_id, estado):
    assert variables(REPO, customer_id).estado_score is estado


def test_vigencia_del_score_sale_de_meta():
    repo = RepositorioMemoria()
    repo.parametros = {**repo.parametros, "score_vigencia_dias": 6}
    assert variables(repo, "CL-1178922").estado_score is EstadoScore.vencido


def test_varias_facturas_vencidas_ordenadas_por_vencimiento():
    cuenta = estado_cuenta(REPO, "CL-1126269")
    assert len(cuenta.facturas_vencidas) == 5
    vencimientos = [f.fecha_vencimiento for f in cuenta.facturas_vencidas]
    assert vencimientos == sorted(vencimientos)
    assert cuenta.dias_mora == 131


def test_pago_parcial_aplicado_descuenta_del_saldo():
    cuenta = estado_cuenta(REPO, "CL-1193431")
    bruto = sum(f.monto for f in cuenta.facturas_vencidas)
    assert cuenta.saldo_vencido == Decimal("21.38") < bruto


def test_pago_en_transito_que_cubre_el_saldo():
    cuenta = estado_cuenta(REPO, "CL-1190560")
    assert cuenta.monto_en_transito == cuenta.saldo_vencido == Decimal("50.29")
    assert cuenta.saldo_tras_transito == Decimal("0.00")
    assert len(cuenta.pagos_en_transito) == 1


def test_pago_en_transito_parcial():
    cuenta = estado_cuenta(REPO, "CL-1173697")
    assert cuenta.monto_en_transito == Decimal("30.00")
    assert cuenta.saldo_tras_transito == Decimal("23.49")


def test_factura_en_disputa_no_suma():
    cuenta = estado_cuenta(REPO, "CL-1161090")
    assert cuenta.saldo_vencido == Decimal("0.00")
    assert cuenta.dias_mora == 0
    assert cuenta.facturas_vencidas == []


def test_cliente_inexistente():
    with pytest.raises(KeyError):
        variables(REPO, "CL-0000000")


def test_transito_de_factura_no_vencida_no_cuenta():
    from datetime import datetime

    from agil.dominio.modelos import Pago
    from agil.dominio.reglas.calendario import ZONA

    repo = RepositorioMemoria()
    antes = estado_cuenta(repo, "CL-1171492").monto_en_transito
    repo._pagos.append(
        Pago(
            pago_id="PG-TEST",
            factura_id="F001-05151584",  # pendiente: aún no vence
            customer_id="CL-1171492",
            fecha=datetime(2026, 11, 5, 10, tzinfo=ZONA),
            monto=Decimal("999.00"),
            canal="app",
            estado="en_transito",
        )
    )
    assert estado_cuenta(repo, "CL-1171492").monto_en_transito == antes


def test_estado_cuenta_de_cliente_inexistente_falla():
    with pytest.raises(KeyError):
        estado_cuenta(RepositorioMemoria(), "CL-0000000")
