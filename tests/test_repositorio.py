"""RepositorioMemoria: búsqueda por teléfono, aislamiento por customer_id y escrituras."""

from datetime import date, datetime
from decimal import Decimal

from agil.dominio.modelos import (
    AceptacionOferta,
    Cola,
    Feedback,
    Handoff,
    LinkPago,
    Nota,
    PromesaPago,
    SolicitudNoContacto,
)
from agil.dominio.repositorio.memoria import RepositorioMemoria

AHORA = datetime.fromisoformat("2026-11-06T09:00:00-05:00")


def test_cliente_por_telefono():
    repo = RepositorioMemoria()
    cliente = repo.clientes()[0]
    assert repo.cliente_por_telefono(cliente.telefono_whatsapp) == cliente
    assert repo.cliente_por_telefono("+507 0000-0000") is None


def test_lecturas_solo_devuelven_datos_del_cliente():
    repo = RepositorioMemoria()
    for c in repo.clientes():
        cid = c.customer_id
        for registros in (
            repo.facturas(cid),
            repo.pagos(cid),
            repo.contactos(cid),
            repo.notas(cid),
        ):
            assert all(r.customer_id == cid for r in registros)
    # cada factura y pago aparece exactamente en su cliente: las listas no están vacías
    assert sum(len(repo.facturas(c.customer_id)) for c in repo.clientes()) == 772
    assert sum(len(repo.pagos(c.customer_id)) for c in repo.clientes()) == 657
    assert repo.cliente("CL-0000000") is None
    assert repo.facturas("CL-0000000") == []
    assert repo.score("CL-0000000") is None


def test_guardar_nota_queda_en_notas_del_cliente():
    repo = RepositorioMemoria()
    cid = "CL-1171492"
    antes = len(repo.notas(cid))
    nota = Nota(nota_id="N-T", customer_id=cid, fecha=AHORA, origen="agente", texto="x", flags=[])
    repo.guardar_nota(nota)
    assert len(repo.notas(cid)) == antes + 1
    assert nota not in repo.notas("CL-1140215")


def test_escrituras_del_agente():
    repo = RepositorioMemoria()
    cid = "CL-1171492"
    promesa = PromesaPago(
        promesa_id="P",
        customer_id=cid,
        fecha_promesa=date(2026, 11, 10),
        monto=Decimal("10.00"),
        creada=AHORA,
    )
    aceptacion = AceptacionOferta(
        aceptacion_id="A",
        customer_id=cid,
        oferta_id="OF-102",
        monto_base=Decimal("10.00"),
        creada=AHORA,
    )
    link = LinkPago(link_id="L", customer_id=cid, monto=Decimal("10.00"), url="u", creado=AHORA)
    feedback = Feedback(feedback_id="F", customer_id=cid, texto="t", etiquetas=[], creado=AHORA)
    handoff = Handoff(
        handoff_id="H", customer_id=cid, cola=Cola.basica, motivo="m", resumen="r", creado=AHORA
    )
    solicitud = SolicitudNoContacto(solicitud_id="S", customer_id=cid, texto="t", creada=AHORA)
    repo.guardar_promesa(promesa)
    repo.guardar_aceptacion(aceptacion)
    repo.guardar_link(link)
    repo.guardar_feedback(feedback)
    repo.guardar_handoff(handoff)
    repo.guardar_solicitud_no_contacto(solicitud)
    assert repo.promesas == [promesa]
    assert repo.aceptaciones == [aceptacion]
    assert repo.links == [link]
    assert repo.feedbacks == [feedback]
    assert repo.handoffs == [handoff]
    assert repo.solicitudes_no_contacto == [solicitud]


def test_pausar_whatsapp_registra_fecha():
    repo = RepositorioMemoria()
    repo.pausar_whatsapp("CL-1171492", date(2026, 11, 6))
    c = repo.cliente("CL-1171492")
    assert c.whatsapp_pausado and c.whatsapp_pausado_desde == date(2026, 11, 6)
    assert repo.cliente_por_telefono(c.telefono_whatsapp) == c


def test_cliente_por_telefono_en_formato_whatsapp():
    repo = RepositorioMemoria()
    assert repo.cliente_por_telefono("50769886979").customer_id == "CL-1019515"


def test_telefono_sin_digitos_no_coincide():
    assert RepositorioMemoria().cliente_por_telefono("sin número") is None


def test_score_y_ofertas_cargados_de_mock():
    repo = RepositorioMemoria()
    assert repo.score("CL-1019515").customer_id == "CL-1019515"
    ofertas = repo.ofertas()
    assert ofertas and ofertas[0].oferta_id == "OF-101"
    ofertas.clear()
    assert repo.ofertas()


def test_meta_cargada():
    repo = RepositorioMemoria()
    assert isinstance(repo.fecha_referencia, date)
    assert isinstance(repo.parametros, dict) and repo.parametros
