from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agil.dominio.modelos import Cargo, LinkPago, Oferta, Pago, Score

OFERTA = {
    "oferta_id": "OF-1",
    "nombre": "Descuento",
    "tipo": "descuento",
    "segmentos_elegibles": ["olvidadizo"],
    "aplica_a": "saldo_vencido",
    "parametros": {"porcentaje_descuento": "10"},
    "monto_min": "10.00",
    "monto_max": "500.00",
    "vigencia_desde": "2026-01-01",
    "vigencia_hasta": "2026-12-31",
    "requiere_aprobacion_humana": False,
    "nota_interna": "solo uso interno",
    "campo_desconocido": 1,
}


def test_montos_string_a_decimal():
    assert Cargo(concepto="x", monto="12.34").monto == Decimal("12.34")


def test_modelo_inmutable():
    c = Cargo(concepto="x", monto="1")
    with pytest.raises(ValidationError):
        c.monto = Decimal("2")


def test_extra_ignorado_y_nota_interna_excluida():
    o = Oferta.model_validate(OFERTA)
    assert o.nota_interna == "solo uso interno"
    dump = o.model_dump(mode="json")
    assert "nota_interna" not in dump and "campo_desconocido" not in dump


AHORA = datetime.fromisoformat("2026-11-06T09:00:00-05:00")
LINK = {"link_id": "LK-1", "customer_id": "CL-1", "monto": "10.00", "url": "u", "creado": AHORA}


def test_monto_float_rechazado():
    with pytest.raises(ValidationError):
        Cargo(concepto="x", monto=12.34)


@pytest.mark.parametrize("monto", ["0", "-1.00"])
def test_escritura_exige_monto_positivo(monto):
    with pytest.raises(ValidationError):
        LinkPago(**{**LINK, "monto": monto})


def test_escritura_rechaza_campos_de_mas():
    with pytest.raises(ValidationError):
        LinkPago(**LINK, descuento="100")


def test_fecha_sin_zona_rechazada():
    with pytest.raises(ValidationError):
        LinkPago(**{**LINK, "creado": datetime(2026, 11, 6, 9)})


def test_estado_fuera_de_catalogo_rechazado():
    with pytest.raises(ValidationError):
        Pago(
            pago_id="P",
            factura_id="F",
            customer_id="C",
            fecha=AHORA,
            monto="1.00",
            canal="app",
            estado="en_transito ",
        )


def test_score_fuera_de_rango_rechazado():
    with pytest.raises(ValidationError):
        Score(
            customer_id="C",
            propension_pago="1.2",
            riesgo_churn="0",
            riesgo_atraso="0",
            fecha_calculo="2026-11-01",
            version_modelo="v",
        )


def test_nota_interna_fuera_del_repr():
    assert "solo uso interno" not in repr(Oferta.model_validate(OFERTA))
