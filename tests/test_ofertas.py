from decimal import Decimal

import pytest

from agil.dominio.datos import RepositorioMemoria
from agil.dominio.modelos import Cargo, Segmento
from agil.dominio.ofertas import ofertas_elegibles, validar_oferta

S = Segmento


@pytest.fixture(scope="module")
def repo():
    return RepositorioMemoria()


def _ids(repo, customer_id, segmento):
    return [o.oferta_id for o in ofertas_elegibles(repo, customer_id, segmento)]


@pytest.mark.parametrize(
    ("customer_id", "segmento", "esperadas"),
    [
        ("CL-1171492", S.olvidadizo, ["OF-101", "OF-102"]),
        ("CL-1152549", S.dificultad_temporal, ["OF-101", "OF-102", "OF-110", "OF-111", "OF-120"]),
        ("CL-1191572", S.reincidente, ["OF-101", "OF-103", "OF-110"]),
        ("CL-1100708", S.valioso_churn, ["OF-101", "OF-111", "OF-120", "OF-130", "OF-131"]),
        ("CL-1140215", S.mora_avanzada, ["OF-101", "OF-112", "OF-140", "OF-141", "OF-142"]),
    ],
)
def test_ofertas_de_candidatos_demo(repo, customer_id, segmento, esperadas):
    assert _ids(repo, customer_id, segmento) == esperadas


def test_oferta_vencida_no_aparece_ni_valida(repo):
    assert "OF-132" not in _ids(repo, "CL-1100708", S.valioso_churn)
    v = validar_oferta(repo, "CL-1100708", S.valioso_churn, "OF-132")
    assert not v.ok and "vigente" in v.motivo


def test_oferta_valida(repo):
    assert validar_oferta(repo, "CL-1171492", S.olvidadizo, "OF-102").ok


def test_oferta_inexistente(repo):
    v = validar_oferta(repo, "CL-1171492", S.olvidadizo, "OF-999")
    assert not v.ok and "no existe" in v.motivo


def test_fuera_de_segmento(repo):
    v = validar_oferta(repo, "CL-1171492", S.olvidadizo, "OF-140")
    assert not v.ok and "segmento" in v.motivo


def test_fuera_de_rango(repo):
    # Saldo 71.04 < 80.00 de OF-111.
    v = validar_oferta(repo, "CL-1191572", S.dificultad_temporal, "OF-111")
    assert not v.ok and "rango" in v.motivo


def test_rango_sobre_factura_vencida_mas_antigua(repo):
    # Saldo 427.89 (> 400) pero la factura vencida más antigua es 103.68: OF-130 aplica.
    assert validar_oferta(repo, "CL-1140215", S.valioso_churn, "OF-130").ok


def test_requiere_aprobacion_humana_escala(repo):
    assert "OF-112" in _ids(repo, "CL-1140215", S.mora_avanzada)
    v = validar_oferta(repo, "CL-1140215", S.mora_avanzada, "OF-112")
    assert not v.ok and "escala" in v.motivo and "humana" in v.motivo


def test_reconexion_sin_cargos_no_aplica(repo):
    assert not validar_oferta(repo, "CL-1100708", S.valioso_churn, "OF-133").ok


def test_cuenta_sin_rango(repo):
    assert validar_oferta(repo, "CL-1215806", S.dificultad_temporal, "OF-120").ok


def test_sin_saldo_no_hay_ofertas(repo):
    sin_deuda = next(
        c.customer_id
        for c in repo.clientes()
        if all(f.estado not in ("vencida", "parcial") for f in repo.facturas(c.customer_id))
    )
    assert _ids(repo, sin_deuda, S.olvidadizo) == []
    assert not validar_oferta(repo, sin_deuda, S.olvidadizo, "OF-101").ok


def test_cliente_desconocido_lanza_key_error(repo):
    with pytest.raises(KeyError):
        ofertas_elegibles(repo, "CL-0000000", S.olvidadizo)
    with pytest.raises(KeyError):
        validar_oferta(repo, "CL-0000000", S.olvidadizo, "OF-101")


def test_motivos_sin_nota_interna(repo):
    notas = {o.nota_interna for o in repo.ofertas() if o.nota_interna}
    for oid in ("OF-112", "OF-113", "OF-120", "OF-132", "OF-140"):
        motivo = validar_oferta(repo, "CL-1191572", S.reincidente, oid).motivo or ""
        assert not any(n in motivo for n in notas)


def test_reconexion_con_cargo_aplica():
    # Los datos mock no traen cargos de reconexión: se agrega uno a la factura vencida más antigua.
    repo = RepositorioMemoria()
    cid = "CL-1100708"
    vieja = min(
        (f for f in repo.facturas(cid) if f.estado in ("vencida", "parcial")),
        key=lambda f: f.fecha_vencimiento,
    )
    cargo = Cargo(concepto="Cargo por reconexión", monto=Decimal("15.00"))
    con_cargo = vieja.model_copy(update={"detalle": [*vieja.detalle, cargo]})
    repo._facturas = [con_cargo if f is vieja else f for f in repo._facturas]
    assert validar_oferta(repo, cid, S.valioso_churn, "OF-133").ok


def test_nota_interna_no_se_serializa(repo):
    assert all("nota_interna" not in o.model_dump() for o in repo.ofertas())


def test_base_factura_vencida_descuenta_pagos_aplicados(repo):
    from agil.dominio.calculos import estado_cuenta, saldo_factura
    from agil.dominio.ofertas import _monto_base

    oferta = next(o for o in repo.ofertas() if o.oferta_id == "OF-130")
    estado = estado_cuenta(repo, "CL-1193431")
    parcial = estado.facturas_vencidas[0]
    base = _monto_base(repo, "CL-1193431", oferta, estado)
    assert parcial.estado == "parcial"
    assert base == saldo_factura(parcial, repo.pagos("CL-1193431")) < parcial.monto


@pytest.mark.parametrize(
    ("oferta_id", "aplica_a"), [("OF-130", "factura_vencida"), ("OF-101", "otro")]
)
def test_base_none_sin_facturas_o_aplica_a_desconocido(repo, oferta_id, aplica_a):
    from agil.dominio.calculos import estado_cuenta
    from agil.dominio.ofertas import _monto_base

    oferta = next(o for o in repo.ofertas() if o.oferta_id == oferta_id)
    oferta = oferta.model_copy(update={"aplica_a": aplica_a})
    estado = estado_cuenta(repo, "CL-1100708").model_copy(update={"facturas_vencidas": []})
    assert _monto_base(repo, "CL-1100708", oferta, estado) is None


def test_pago_en_transito_que_cubre_el_saldo_no_abre_ofertas(repo):
    # CL-1190560: "ya pagué" el 4-nov; el pago en tránsito cubre todo el saldo
    assert ofertas_elegibles(repo, "CL-1190560", Segmento.olvidadizo) == []
