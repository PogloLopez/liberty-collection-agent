from datetime import timedelta
from decimal import Decimal

import pytest

from agil.agente import tools as tools_mod
from agil.agente.sesion import Sesion
from agil.agente.tools import cifras_oferta, crear_tools, prefijo, texto_tarjeta_oferta
from agil.dominio.modelos import Cola, EtiquetaFeedback, FlagMemoria, Segmento, Validacion
from agil.dominio.reglas.ofertas import condiciones


def _sesion(customer_id="CL-1140215", segmento=Segmento.mora_avanzada, cola=Cola.especializada):
    return Sesion(
        conversacion_id="CV-T",
        customer_id=customer_id,
        segmento=segmento,
        cola=cola,
        max_turnos=10,
        max_caracteres=400,
        verificada=True,
    )


@pytest.fixture
def sesion():
    return _sesion()


@pytest.fixture
def tools(repo, sesion, ahora):
    return {t.tool_name: t for t in crear_tools(repo, sesion, ahora)}


def test_nueve_tools_sin_customer_id(tools):
    assert len(tools) == 9
    for t in tools.values():
        assert "customer_id" not in t.tool_spec["inputSchema"]["json"].get("properties", {})


def test_consultar_saldo_devuelve_cifras_con_placeholders(tools, sesion):
    r = tools["consultar_saldo"]()
    assert r["cifras"]["{{saldo_vencido}}"] == "$427.89"
    assert r["cifras"]["{{plazo_aplicacion}}"] == "1 a 3 días hábiles"
    assert sesion.valores["saldo_vencido"] == "$427.89"
    assert {"periodo_factura", "fecha_vencimiento", "dias_mora"} <= sesion.valores.keys()


def test_ofertas_ordenadas_de_menos_a_mas_generosa(tools, sesion):
    r = tools["consultar_ofertas_elegibles"]()
    ids = [o["oferta_id"] for o in r["ofertas"]]
    assert ids == ["OF-101", "OF-112", "OF-140", "OF-142", "OF-141"]
    of140 = r["ofertas"][2]["cifras"]
    assert of140["{{of_140.porcentaje_descuento}}"] == "20%"
    assert of140["{{of_140.monto_a_pagar}}"] == "$342.31"
    assert "nota_interna" not in str(r)
    assert sesion.valores["of_142.monto_cuota"] == "$160.46"


def test_cifras_oferta_solo_campos_que_aplican(repo):
    oferta = next(o for o in repo.ofertas() if o.oferta_id == "OF-101")
    assert set(cifras_oferta(condiciones(repo, "CL-1140215", oferta))) == {"of_101.monto_a_pagar"}


def test_aceptar_oferta_solo_crea_la_tarjeta(tools, sesion, repo):
    tools["aceptar_oferta"](oferta_id="OF-140")
    assert sesion.tarjeta.tipo == "oferta" and sesion.tarjeta.monto == Decimal("342.31")
    assert "Total a pagar: $342.31" in sesion.tarjeta.texto
    assert repo.aceptaciones == []


def test_promesa_valida_la_ventana(repo, ahora):
    sesion = _sesion("CL-1171492", Segmento.olvidadizo, Cola.basica)
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    afuera = (repo.fecha_referencia + timedelta(days=9)).isoformat()
    assert "ventana" in t["registrar_promesa_pago"](fecha=afuera)
    assert "AAAA-MM-DD" in t["registrar_promesa_pago"](fecha="el miércoles")
    assert sesion.tarjeta is None
    dentro = (repo.fecha_referencia + timedelta(days=3)).isoformat()
    t["registrar_promesa_pago"](fecha=dentro)
    assert sesion.tarjeta.tipo == "promesa" and sesion.tarjeta.monto == Decimal("76.40")
    assert "fecha_promesa" in sesion.valores and repo.promesas == []


def test_link_por_la_oferta_aceptada_e_idempotente(tools, sesion, repo):
    sesion.oferta_aceptada = condiciones(
        repo, "CL-1140215", next(o for o in repo.ofertas() if o.oferta_id == "OF-142")
    )
    r1 = tools["generar_link_pago"]()
    r2 = tools["generar_link_pago"]()
    assert r1 == r2 and r1["cifras"]["{{monto_link}}"] == "$160.46"
    assert len(repo.links) == 1 and repo.links[0].monto == Decimal("160.46")


def test_link_sin_saldo(repo, ahora):
    sesion = _sesion()
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    repo._pagos = [p.model_copy(update={"estado": "aplicado"}) for p in repo._pagos]
    repo._facturas = [f for f in repo._facturas if f.customer_id != "CL-1140215"]
    assert "error" in t["generar_link_pago"]()


def test_nota_y_feedback_idempotentes(tools, repo):
    antes = len(repo.notas("CL-1140215"))
    for _ in range(2):
        tools["guardar_nota"](texto="Cobra en quincena", flags=[FlagMemoria.fecha_pago_desfasada])
        tools["registrar_feedback_cliente"](
            texto="El internet falla", etiquetas=[EtiquetaFeedback.queja_servicio]
        )
    assert len(repo.notas("CL-1140215")) == antes + 1 and len(repo.feedbacks) == 1


@pytest.mark.parametrize(
    ("motivo", "cola"),
    [("disputa", Cola.reclamos), ("vulnerable", Cola.especializada), ("otro", Cola.basica)],
)
def test_escalar_elige_cola_y_cierra(repo, ahora, motivo, cola):
    sesion = _sesion("CL-1171492", Segmento.olvidadizo, Cola.basica)
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    t["escalar_a_humano"](motivo=motivo, resumen="Pide un asesor.")
    assert repo.handoffs[0].cola == cola and sesion.cerrada


def test_derivar_pausa_whatsapp_y_cierra(tools, sesion, repo):
    tools["derivar_solicitud_contacto"](texto="no me escriban hoy por aquí")
    assert repo.cliente("CL-1140215").whatsapp_pausado
    assert sesion.cerrada and sesion.motivo_cierre == "no_contactar"
    assert len(repo.solicitudes_no_contacto) == 1


def test_link_vuelve_a_su_url_al_repetir_un_monto(tools, sesion, repo):
    r1 = tools["generar_link_pago"]()
    sesion.oferta_aceptada = condiciones(
        repo, "CL-1140215", next(o for o in repo.ofertas() if o.oferta_id == "OF-142")
    )
    tools["generar_link_pago"]()
    sesion.oferta_aceptada = None
    assert tools["generar_link_pago"]() == r1 and len(repo.links) == 2


def test_escritura_fallida_se_puede_reintentar(tools, repo, monkeypatch):
    def falla(nota):
        raise RuntimeError("base caída")

    monkeypatch.setattr(repo, "guardar_nota", falla)
    with pytest.raises(RuntimeError):
        tools["guardar_nota"](texto="x", flags=[])
    monkeypatch.undo()
    antes = len(repo.notas("CL-1140215"))
    tools["guardar_nota"](texto="x", flags=[])
    assert len(repo.notas("CL-1140215")) == antes + 1


def test_promesa_con_oferta_en_su_fecha_limite(repo, ahora):
    sesion = _sesion("CL-1152549", Segmento.dificultad_temporal, Cola.basica)
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    tarde = (repo.fecha_referencia + timedelta(days=5)).isoformat()
    assert sesion.tarjeta is None
    t["registrar_promesa_pago"](fecha=tarde, oferta_id="OF-102")
    assert sesion.tarjeta is not None


@pytest.mark.parametrize(
    ("oferta_id", "esperado"),
    [
        ("OF-101", "Pago total con link. Total a pagar: $427.89."),
        ("OF-102", "Total a pagar: $427.89. Fecha límite: miércoles 11 de noviembre."),
        ("OF-112", "Plan de 6 cuotas. Paga 6 cuotas: de $71.31 y la última de $71.34."),
        ("OF-120", "Cambio de fecha de corte."),
        ("OF-130", "Descuento de $10.37. Total a pagar: $417.52."),
        ("OF-131", "Descuento de 15% en su cargo mensual. Total a pagar: $427.89."),
        ("OF-140", "Descuento de $85.58. Total a pagar: $342.31."),
        ("OF-142", "Descuento de $106.97. Paga 2 cuotas de $160.46."),
    ],
)
def test_texto_tarjeta_por_tipo_de_oferta(repo, oferta_id, esperado):
    oferta = next(o for o in repo.ofertas() if o.oferta_id == oferta_id)
    texto = texto_tarjeta_oferta(oferta, condiciones(repo, "CL-1140215", oferta))
    assert texto.startswith(f"{oferta.nombre}.") and texto.endswith(esperado)
    if oferta.tipo == "cambio_fecha_corte":
        assert "$" not in texto


def test_ninguna_tool_devuelve_nota_interna(repo, ahora):
    notas = [o.nota_interna for o in repo.ofertas() if o.nota_interna]
    sesion = _sesion()
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    dentro = (repo.fecha_referencia + timedelta(days=2)).isoformat()
    salidas = [
        t["consultar_saldo"](),
        t["consultar_ofertas_elegibles"](),
        t["aceptar_oferta"](oferta_id="OF-140"),
        t["registrar_promesa_pago"](fecha=dentro, oferta_id="OF-140"),
        t["generar_link_pago"](),
        t["guardar_nota"](texto="x", flags=[]),
        t["registrar_feedback_cliente"](texto="x", etiquetas=[]),
        t["escalar_a_humano"](motivo="otro", resumen="x"),
        t["derivar_solicitud_contacto"](texto="x"),
    ]
    todo = str(salidas) + sesion.model_dump_json()
    assert notas and "nota_interna" not in todo
    assert not any(n in todo for n in notas)


def _ventana_abierta(monkeypatch):
    """Con los mocks la ventana coincide con la prórroga: se abre para probar el respaldo."""
    monkeypatch.setattr(tools_mod, "validar_fecha_promesa", lambda *a: Validacion(ok=True))


def test_promesa_con_oferta_despues_de_su_fecha_limite(repo, ahora, monkeypatch):
    _ventana_abierta(monkeypatch)
    sesion = _sesion("CL-1152549", Segmento.dificultad_temporal, Cola.basica)
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    tarde = (repo.fecha_referencia + timedelta(days=6)).isoformat()
    assert "fecha límite" in t["registrar_promesa_pago"](fecha=tarde, oferta_id="OF-102")
    assert sesion.tarjeta is None


def test_promesa_sin_saldo(repo, ahora, monkeypatch):
    _ventana_abierta(monkeypatch)
    sesion = _sesion()
    t = {x.tool_name: x for x in crear_tools(repo, sesion, ahora)}
    repo._pagos = [p.model_copy(update={"estado": "aplicado"}) for p in repo._pagos]
    repo._facturas = [f for f in repo._facturas if f.customer_id != "CL-1140215"]
    dentro = (repo.fecha_referencia + timedelta(days=2)).isoformat()
    assert "No hay saldo" in t["registrar_promesa_pago"](fecha=dentro)
    assert sesion.tarjeta is None


def test_escalar_y_derivar_idempotentes(tools, sesion, repo):
    for _ in range(2):
        tools["escalar_a_humano"](motivo="pide_humano", resumen="x")
        tools["derivar_solicitud_contacto"](texto="x")
    assert len(repo.handoffs) == 1 and len(repo.solicitudes_no_contacto) == 1
    assert sesion.motivo_cierre == "handoff"  # el primer motivo de cierre se conserva


def test_escalar_pide_humano_usa_la_cola_de_la_sesion(tools, repo):
    tools["escalar_a_humano"](motivo="pide_humano", resumen="x")
    assert repo.handoffs[0].cola == Cola.especializada
    assert repo.handoffs[0].motivo == "pide_humano"


def test_prefijo_de_placeholders():
    assert prefijo("OF-104") == "of_104"


def test_tarjeta_muestra_la_ultima_cuota_si_difiere(repo):
    from agil.agente.tools import texto_tarjeta_oferta

    o = next(o for o in repo.ofertas() if o.oferta_id == "OF-112")
    texto = texto_tarjeta_oferta(o, condiciones(repo, "CL-1140215", o))
    assert "6 cuotas: de $71.31 y la última de $71.34" in texto
