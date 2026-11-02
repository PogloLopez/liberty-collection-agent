from datetime import timedelta
from decimal import Decimal

import pytest

from agil.dominio.modelos import Cargo, Pago, Segmento
from agil.dominio.reglas.calculos import estado_cuenta
from agil.dominio.reglas.ofertas import (
    condiciones,
    dias_prorroga,
    ofertas_elegibles,
    validar_fecha_promesa,
    validar_oferta,
)
from agil.dominio.repositorio.memoria import RepositorioMemoria

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
        # 41 y 22 días de mora: superan el tope de la prórroga de OF-102 (30) y OF-103 (15).
        ("CL-1152549", S.dificultad_temporal, ["OF-101", "OF-110", "OF-111", "OF-120"]),
        ("CL-1191572", S.reincidente, ["OF-101", "OF-110"]),
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
    from agil.dominio.reglas.calculos import estado_cuenta, saldo_factura
    from agil.dominio.reglas.ofertas import _monto_base

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
    from agil.dominio.reglas.calculos import estado_cuenta
    from agil.dominio.reglas.ofertas import _monto_base

    oferta = next(o for o in repo.ofertas() if o.oferta_id == oferta_id)
    oferta = oferta.model_copy(update={"aplica_a": aplica_a})
    estado = estado_cuenta(repo, "CL-1100708").model_copy(update={"facturas_vencidas": []})
    assert _monto_base(repo, "CL-1100708", oferta, estado) is None


def test_pago_en_transito_que_cubre_el_saldo_no_abre_ofertas(repo):
    # CL-1190560: "ya pagué" el 4-nov; el pago en tránsito cubre todo el saldo
    assert ofertas_elegibles(repo, "CL-1190560", Segmento.olvidadizo) == []


def _oferta(repo, oferta_id):
    return next(o for o in repo.ofertas() if o.oferta_id == oferta_id)


def test_condiciones_liquidacion_en_cuotas(repo):
    c = condiciones(repo, "CL-1140215", _oferta(repo, "OF-142"))
    assert c.monto_base == Decimal("427.89")
    assert c.monto_descuento == Decimal("106.97")
    assert c.monto_a_pagar == Decimal("320.92")
    assert (c.numero_cuotas, c.monto_cuota) == (2, Decimal("160.46"))
    assert c.primer_pago == Decimal("160.46")


def test_cuotas_suman_exacto(repo):
    c = condiciones(repo, "CL-1140215", _oferta(repo, "OF-112"))
    assert (c.monto_cuota, c.monto_ultima_cuota) == (Decimal("71.31"), Decimal("71.34"))
    assert c.monto_cuota * 5 + c.monto_ultima_cuota == c.monto_a_pagar
    assert c.monto_descuento is None


def test_descuento_sobre_lo_que_queda_tras_el_transito():
    repo = RepositorioMemoria()
    factura = repo.facturas("CL-1140215")[-1]
    repo._pagos.append(
        Pago(
            pago_id="PG-TEST",
            factura_id=factura.factura_id,
            customer_id="CL-1140215",
            fecha="2026-11-05T10:00:00-05:00",
            monto=Decimal("27.89"),
            canal="app",
            estado="en_transito",
        )
    )
    c = condiciones(repo, "CL-1140215", _oferta(repo, "OF-140"))
    assert c.monto_descuento == Decimal("80.00")  # 20 % de 400.00, no de 427.89
    assert c.monto_a_pagar == Decimal("320.00")


def test_condiciones_prorroga_da_fecha_limite(repo):
    c = condiciones(repo, "CL-1171492", _oferta(repo, "OF-102"))
    assert c.fecha_limite == repo.fecha_referencia + timedelta(days=5)
    assert c.primer_pago == c.monto_a_pagar == Decimal("76.40")


def test_descuento_al_cargo_mensual_no_cambia_lo_que_se_paga_hoy(repo):
    c = condiciones(repo, "CL-1100708", _oferta(repo, "OF-131"))
    assert c.monto_a_pagar == Decimal("141.13")
    assert c.monto_descuento == Decimal("21.17")


def test_condiciones_descuentan_el_pago_en_transito(repo):
    c = condiciones(repo, "CL-1173697", _oferta(repo, "OF-101"))
    assert c.monto_base == Decimal("53.49") and c.monto_a_pagar == Decimal("23.49")


def test_condiciones_de_oferta_que_no_aplica(repo):
    with pytest.raises(ValueError):
        condiciones(repo, "CL-1100708", _oferta(repo, "OF-133"))


@pytest.mark.parametrize(("dias", "ok"), [(0, False), (1, True), (5, True), (6, False)])
def test_ventana_de_la_promesa(repo, dias, ok):
    fecha = repo.fecha_referencia + timedelta(days=dias)
    v = validar_fecha_promesa(repo, "CL-1171492", S.olvidadizo, fecha)
    assert v.ok is ok and (ok or "ventana" in v.motivo)


def test_promesa_sin_prorroga_aprobada(repo):
    fecha = repo.fecha_referencia + timedelta(days=1)
    v = validar_fecha_promesa(repo, "CL-1140215", S.mora_avanzada, fecha)
    assert not v.ok and "prórroga" in v.motivo


def _todas_las_condiciones(repo):
    for c in repo.clientes():
        for seg in Segmento:
            for o in ofertas_elegibles(repo, c.customer_id, seg):
                yield c.customer_id, o, condiciones(repo, c.customer_id, o)


def test_invariantes_de_condiciones_en_todo_el_mock(repo):
    vistas = 0
    for cid, o, c in _todas_las_condiciones(repo):
        vistas += 1
        assert c.monto_a_pagar >= 0, (cid, o.oferta_id)
        assert c.monto_a_pagar <= estado_cuenta(repo, cid).saldo_tras_transito
        if c.monto_descuento is not None and o.aplica_a != "cargo_mensual":
            assert c.monto_descuento <= c.monto_base
        if c.numero_cuotas:
            n = c.numero_cuotas
            assert c.monto_cuota * (n - 1) + c.monto_ultima_cuota == c.monto_a_pagar
            assert 0 <= c.monto_ultima_cuota - c.monto_cuota < Decimal("0.01") * n
            assert c.monto_cuota.as_tuple().exponent == -2
    assert vistas > 0


def test_sin_descuento_ni_cuotas_paga_el_saldo_tras_transito(repo):
    for cid, _o, c in _todas_las_condiciones(repo):
        if c.monto_descuento is None:
            assert c.monto_a_pagar == estado_cuenta(repo, cid).saldo_tras_transito
        if not c.numero_cuotas:
            assert c.monto_cuota is None and c.monto_ultima_cuota is None
        if not c.dias_prorroga:
            assert c.fecha_limite is None


def test_reconexion_al_cien_por_ciento_resta_todo_el_cargo():
    repo = RepositorioMemoria()
    cid = "CL-1100708"
    vieja = min(
        (f for f in repo.facturas(cid) if f.estado in ("vencida", "parcial")),
        key=lambda f: f.fecha_vencimiento,
    )
    cargo = Cargo(concepto="Cargo por reconexión", monto=Decimal("15.00"))
    con_cargo = vieja.model_copy(update={"detalle": [*vieja.detalle, cargo]})
    repo._facturas = [con_cargo if f is vieja else f for f in repo._facturas]
    saldo = estado_cuenta(repo, cid).saldo_tras_transito
    c = condiciones(repo, cid, _oferta(repo, "OF-133"))
    assert c.monto_base == c.monto_descuento == Decimal("15.00")
    assert c.monto_a_pagar == saldo - Decimal("15.00")


def test_cargo_mensual_descuenta_sobre_arpu(repo):
    c = condiciones(repo, "CL-1100708", _oferta(repo, "OF-131"))
    assert c.monto_base == repo.cliente("CL-1100708").arpu_usd
    assert c.monto_a_pagar == estado_cuenta(repo, "CL-1100708").saldo_tras_transito


def test_descuento_redondea_al_centavo(repo):
    # 20 % de 427.89 = 85.578 -> 85.58
    c = condiciones(repo, "CL-1140215", _oferta(repo, "OF-140"))
    assert c.monto_descuento == Decimal("85.58")
    assert c.monto_a_pagar == Decimal("342.31")


def test_ventana_usa_la_prorroga_maxima_de_las_elegibles():
    # Se añade una prórroga más larga para el segmento: la ventana debe crecer hasta ella.
    repo = RepositorioMemoria()
    of102 = _oferta(repo, "OF-102")
    larga = of102.model_copy(
        update={
            "oferta_id": "OF-TEST",
            "parametros": of102.parametros.model_copy(update={"dias_prorroga": 10}),
        }
    )
    repo._ofertas = [*repo._ofertas, larga]
    hoy = repo.fecha_referencia
    assert validar_fecha_promesa(repo, "CL-1171492", S.olvidadizo, hoy + timedelta(days=10)).ok
    assert not validar_fecha_promesa(repo, "CL-1171492", S.olvidadizo, hoy + timedelta(days=11)).ok


def _repo_con_tope(tope):
    repo = RepositorioMemoria()
    of102 = _oferta(repo, "OF-102")
    par = of102.parametros.model_copy(update={"dias_mora_max": tope})
    repo._ofertas = [of102.model_copy(update={"parametros": par})]
    return repo


@pytest.mark.parametrize(("tope", "dias"), [(30, 5), (15, 3)])
def test_la_prorroga_se_recorta_al_tope_de_mora(tope, dias):
    # CL-1171492 lleva 12 días de mora; la prórroga cuenta desde hoy hasta el tope.
    repo = _repo_con_tope(tope)
    hoy = repo.fecha_referencia
    c = condiciones(repo, "CL-1171492", repo._ofertas[0])
    assert c.dias_prorroga == dias and c.fecha_limite == hoy + timedelta(days=dias)
    assert validar_fecha_promesa(repo, "CL-1171492", S.olvidadizo, hoy + timedelta(days=dias)).ok
    fuera = hoy + timedelta(days=dias + 1)
    assert not validar_fecha_promesa(repo, "CL-1171492", S.olvidadizo, fuera).ok


def test_sin_dias_de_prorroga_la_oferta_no_es_elegible():
    repo = _repo_con_tope(12)
    assert _ids(repo, "CL-1171492", S.olvidadizo) == []
    assert "supera la mora" in validar_oferta(repo, "CL-1171492", S.olvidadizo, "OF-102").motivo


@pytest.mark.parametrize(("tope", "dias"), [(30, 5), (3, 3), (0, 0)])
def test_prorroga_sin_mora_solo_la_recorta_el_tope(repo, tope, dias):
    oferta = _oferta(repo, "OF-102")
    oferta = oferta.model_copy(
        update={"parametros": oferta.parametros.model_copy(update={"dias_mora_max": tope})}
    )
    estado = estado_cuenta(repo, "CL-1171492").model_copy(update={"dias_mora": 0})
    assert dias_prorroga(oferta, estado) == dias


def test_tope_de_mora_sin_prorroga_da_cero_y_no_rechaza(repo):
    of101 = _oferta(repo, "OF-101")
    assert not of101.parametros.dias_prorroga
    par = of101.parametros.model_copy(update={"dias_mora_max": 1})
    of101 = of101.model_copy(update={"parametros": par})
    estado = estado_cuenta(repo, "CL-1171492")  # 12 días de mora, por encima del tope
    assert dias_prorroga(of101, estado) == 0
    otro = RepositorioMemoria()
    otro._ofertas = [of101]
    assert _ids(otro, "CL-1171492", S.olvidadizo) == ["OF-101"]
    c = condiciones(otro, "CL-1171492", of101)
    assert c.dias_prorroga is None and c.fecha_limite is None


def test_promesa_en_el_pasado_se_rechaza(repo):
    fecha = repo.fecha_referencia - timedelta(days=1)
    v = validar_fecha_promesa(repo, "CL-1171492", S.olvidadizo, fecha)
    assert not v.ok and "ventana" in v.motivo


def test_promesa_cliente_desconocido_lanza_key_error(repo):
    with pytest.raises(KeyError):
        validar_fecha_promesa(repo, "CL-0000000", S.olvidadizo, repo.fecha_referencia)
