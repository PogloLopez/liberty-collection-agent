import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from conftest import ModeloGuionado

from agil.agente.config import Modelos
from agil.agente.orquestador import TEXTOS, Orquestador
from agil.agente.sesion import Sesion
from agil.agente.tools import CONFIRMA_PROMESA
from agil.dominio.harness.identidad import ultimos_cuatro
from agil.dominio.harness.intenciones import Boton
from agil.dominio.modelos import Pago
from agil.dominio.reglas.calculos import estado_cuenta

CID = "CL-1171492"  # olvidadizo, con prórroga de 5 días
CID_DIFICULTAD = "CL-1173697"  # dificultad_temporal: elegible a OF-110 y OF-120


def _orq(repo, ahora, agente, estratega=None, moderador=None):
    return Orquestador(repo, Modelos(agente, estratega, moderador), ahora)


def _digitos(repo, cid=CID):
    return ultimos_cuatro(repo.cliente(cid).cedula)


def test_excluido_no_se_atiende(repo, ahora):
    excluido = next(c for c in repo.clientes() if c.flags.reclamo_abierto)
    with pytest.raises(ValueError):
        _orq(repo, ahora, ModeloGuionado()).iniciar(excluido.customer_id, "CV-1")


def test_flujo_verificacion_link_y_render(repo, ahora):
    agente = ModeloGuionado(
        "Hola, Itzel. ¿Me confirma los últimos cuatro dígitos de su cédula?",
        ("generar_link_pago", {}),
        "Gracias. Puede pagar {{monto_link}} aquí: {{link_pago}}",
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1", "Hola, tiene un saldo pendiente.")
    r1 = orq.atender(sesion, "se me pasó, cómo pago")
    assert "cuatro dígitos" in r1.mensajes[0] and sesion.cedula_pedida
    r2 = orq.atender(sesion, _digitos(repo))
    assert sesion.verificada
    assert r2.mensajes == [f"Gracias. Puede pagar $76.40 aquí: {repo.links[0].url}"]
    recibido = agente.todo_lo_recibido()
    assert _digitos(repo) not in recibido  # D24: la cédula nunca llega al LLM
    assert "Verificación de cédula correcta" in recibido
    assert "plantilla de primer contacto" in recibido


def test_digitos_sin_pedir_se_enmascaran_y_no_verifican(repo, ahora):
    agente = ModeloGuionado("Gracias por escribir.")
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    orq.atender(sesion, f"mi cédula termina en {_digitos(repo)}")
    assert not sesion.verificada and _digitos(repo) not in agente.todo_lo_recibido()


def test_verificacion_fallida_cuenta_intentos(repo, ahora):
    orq = _orq(repo, ahora, ModeloGuionado())
    sesion = orq.iniciar(CID, "CV-1")
    sesion.cedula_pedida = True
    malos = "0000" if _digitos(repo) != "0000" else "1111"
    for _ in range(3):
        orq.atender(sesion, malos)
    assert sesion.intentos_cedula == 3 and not sesion.verificada and not sesion.cedula_pedida


def test_no_contactar_explicito_sin_llm(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(
        repo,
        ahora,
        agente,
        estratega=ModeloGuionado(
            '{"texto": "Pidió no contacto.", "flags": ["solicita_no_contacto"]}'
        ),
    )
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "No me escriban más")
    assert r.mensajes == [TEXTOS["no_contactar"]] and r.cerrada
    assert agente.recibido == []
    assert repo.cliente(CID).whatsapp_pausado
    nota = repo.notas(CID)[-1]
    assert nota.origen == "sistema" and nota.flags == ["solicita_no_contacto"]  # D34


def test_tarjeta_y_boton_confirmar_registra(repo, ahora):
    agente = ModeloGuionado(
        ("registrar_promesa_pago", {"fecha": "2026-11-11"}),
        "Listo, quedó registrada para el {{fecha_promesa}}.",
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    r1 = orq.atender(sesion, "le pago el miércoles")
    assert r1.tarjeta.texto == (
        f"Promesa de pago de $76.40 para el miércoles 11 de noviembre. {CONFIRMA_PROMESA}"
    )
    assert r1.mensajes == [] and len(agente.recibido) == 1  # T1: la tarjeta cierra el turno
    assert repo.promesas == []
    r2 = orq.atender(sesion, boton=Boton.confirmar)
    url = repo.links[-1].url
    assert r2.mensajes == [
        "Listo, Itzel. Quedó registrada su promesa de pago de $76.40 para el miércoles 11 de "
        f"noviembre. Ese día puede pagar con este link: {url}. ¿Le ayudo con algo más?"
    ]
    assert len(repo.promesas) == 1 and str(repo.promesas[0].monto) == "76.40"
    assert len(agente.recibido) == 1 and sesion.turno == 1  # Confirmar no llama al LLM
    orq.atender(sesion, "gracias")
    assert "confirmó la tarjeta" in agente.todo_lo_recibido()
    assert orq.atender(sesion, boton=Boton.confirmar).mensajes == [TEXTOS["sin_tarjeta"]]
    assert len(repo.promesas) == 1


def test_boton_cancelar_no_registra(repo, ahora):
    agente = ModeloGuionado(("aceptar_oferta", {"oferta_id": "OF-102"}), "Entendido.")
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    orq.atender(sesion, "quiero la prórroga")
    orq.atender(sesion, boton=Boton.cancelar)
    assert repo.aceptaciones == [] and sesion.oferta_aceptada is None
    assert "canceló la tarjeta" in agente.todo_lo_recibido()


def test_validador_reintenta_una_vez_y_limpia_el_historial(repo, ahora):
    agente = ModeloGuionado("Su saldo es $76.40.", "Le comparto su saldo en un momento.")
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "cuánto debo")
    assert r.mensajes == ["Le comparto su saldo en un momento."]
    assert "no se envió" in agente.todo_lo_recibido()
    historial = str(sesion.historial)
    assert "$76.40" not in historial and "no se envió" not in historial


def test_dos_salidas_invalidas_van_a_humano(repo, ahora):
    orq = _orq(repo, ahora, ModeloGuionado("Son $76.40.", "Son 76 dólares."))
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "cuánto debo")
    assert r.mensajes == [TEXTOS["fallo"]] and r.cerrada
    assert repo.handoffs[0].motivo == "fallo_agente"


def test_tope_de_turnos_cierra_el_codigo(repo, ahora):
    orq = _orq(repo, ahora, ModeloGuionado())
    sesion = orq.iniciar(CID, "CV-1")
    for _ in range(sesion.max_turnos):
        assert not orq.atender(sesion, "hola").cerrada
    r = orq.atender(sesion, "hola")
    assert r.mensajes == [TEXTOS["tope"]] and sesion.motivo_cierre == "tope"
    assert orq.atender(sesion, "hola").mensajes == []


def test_contexto_avisa_los_ultimos_turnos(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.turno = sesion.max_turnos - 2
    orq.atender(sesion, "hola")
    assert "Quedan pocos turnos" in agente.todo_lo_recibido()


def test_estratega_inyecta_su_tarjeta(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente, estratega=ModeloGuionado("pago_reciente"))
    sesion = orq.iniciar(CID, "CV-1")
    orq.atender(sesion, "ya pagué")
    assert "[estrategia: pago_reciente]" in agente.todo_lo_recibido()


def test_tres_strikes_cierran_sin_humano(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente, moderador=ModeloGuionado("1", "1", "1"))
    sesion = orq.iniciar(CID, "CV-1")
    assert orq.atender(sesion, "insulto").mensajes == [TEXTOS["abuso"]]
    orq.atender(sesion, "insulto")
    r = orq.atender(sesion, "insulto")
    assert r.mensajes == [TEXTOS["abuso_cierre"]] and r.cerrada
    assert agente.recibido == [] and repo.handoffs == []


def test_cierre_por_tool_deja_resumen(repo, ahora):
    agente = ModeloGuionado(
        ("escalar_a_humano", {"motivo": "pide_humano", "resumen": "Pide asesor."}),
        "Un asesor le escribirá.",
    )
    estratega = ModeloGuionado("pide_humano", '{"texto": "Pidió un asesor.", "flags": []}')
    orq = _orq(repo, ahora, agente, estratega=estratega)
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "quiero hablar con una persona")
    assert r.cerrada and sesion.motivo_cierre == "handoff"
    assert repo.notas(CID)[-1].texto == "Pidió un asesor."


def test_dos_numeros_se_enmascaran_aunque_no_sea_intento(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente, moderador=ModeloGuionado("0"))
    sesion = orq.iniciar(CID, "CV-1")
    orq.atender(sesion, "mi cédula es 8-765-1043 y mi teléfono 6123 4567")
    recibido = agente.todo_lo_recibido() + orq.modelos.moderador.todo_lo_recibido()
    assert "1043" not in recibido and "6123" not in recibido


def test_cedula_tras_verificar_tambien_se_enmascara(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    orq.atender(sesion, "mi cédula completa es 8-765-1043")
    assert "765-1043" not in agente.todo_lo_recibido()


def test_tool_de_cierre_con_texto_invalido_no_reintenta_ni_duplica(repo, ahora):
    agente = ModeloGuionado(
        ("escalar_a_humano", {"motivo": "pide_humano", "resumen": "x"}),
        "Un asesor le escribirá en 5 minutos.",
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "quiero un humano")
    assert r.mensajes == [TEXTOS["handoff"]] and r.cerrada
    assert len(repo.handoffs) == 1 and sesion.motivo_cierre == "handoff"
    assert "no se envió" not in agente.todo_lo_recibido()


class ModeloRoto(ModeloGuionado):
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        raise RuntimeError("sin servicio")
        yield


def test_cedula_no_llega_al_estratega_ni_al_resumen(repo, ahora):
    agente = ModeloGuionado("¿Me confirma los últimos cuatro dígitos de su cédula?", "Gracias.")
    estratega = ModeloGuionado("duda", "duda", '{"texto": "Verificó.", "flags": []}')
    orq = _orq(repo, ahora, agente, estratega=estratega)
    sesion = orq.iniciar(CID, "CV-1")
    orq.atender(sesion, "hola")
    orq.atender(sesion, _digitos(repo))
    assert sesion.verificada
    orq.cerrar(sesion, "fin")
    assert len(estratega.recibido) == 3  # dos estrategias y el resumen
    assert _digitos(repo) not in estratega.todo_lo_recibido()
    assert _digitos(repo) not in str(sesion.transcripcion)


def test_sesion_serializable_y_reanudable(repo, ahora):
    agente = ModeloGuionado(
        ("registrar_promesa_pago", {"fecha": "2026-11-11"}),
        "Confirme con el botón, por favor.",
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1", "Hola.")
    sesion.verificada = True
    orq.atender(sesion, "le pago el miércoles")
    guardada = json.loads(json.dumps(sesion.model_dump(mode="json")))
    reanudada = Sesion.model_validate(guardada)
    assert reanudada.tarjeta == sesion.tarjeta and reanudada.historial

    agente2 = ModeloGuionado("De nada.")
    orq2 = _orq(repo, ahora, agente2)
    r = orq2.atender(reanudada, boton=Boton.confirmar)
    assert "miércoles 11 de noviembre" in r.mensajes[0] and len(repo.promesas) == 1
    orq2.atender(reanudada, "gracias")
    assert "le pago el miércoles" in agente2.todo_lo_recibido()  # el historial sigue


def test_boton_sin_tarjeta_no_llama_al_agente_ni_cuenta_turno(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, boton=Boton.confirmar)
    assert r.mensajes == [TEXTOS["sin_tarjeta"]] and not r.cerrada
    assert agente.recibido == [] and sesion.turno == 0
    assert repo.promesas == [] and repo.aceptaciones == []


def test_excepcion_del_modelo_va_a_humano(repo, ahora):
    orq = _orq(repo, ahora, ModeloRoto())
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "hola")
    assert r.mensajes == [TEXTOS["fallo"]] and r.cerrada
    assert sesion.motivo_cierre == "fallo"
    assert [h.motivo for h in repo.handoffs] == ["fallo_agente"]


def test_fallo_del_estratega_y_moderador_no_bloquea(repo, ahora):
    agente = ModeloGuionado("Hola.")
    orq = _orq(repo, ahora, agente, estratega=ModeloRoto(), moderador=ModeloRoto())
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "hola")
    assert r.mensajes == ["Hola."] and not r.cerrada


def test_eventos_se_vacian_tras_el_turno(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1", "Hola, tiene un saldo pendiente.")
    assert sesion.eventos
    orq.atender(sesion, "hola")
    assert sesion.eventos == []
    orq.atender(sesion, "otra vez")
    ultimo = json.dumps(agente.recibido[-1][1][-1], ensure_ascii=False)
    assert "plantilla de primer contacto" not in ultimo


def test_tope_cuenta_el_boton_cancelar(repo, ahora):
    agente = ModeloGuionado(
        ("registrar_promesa_pago", {"fecha": "2026-11-11"}), "Confirme con el botón."
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    sesion.turno = sesion.max_turnos - 1
    assert orq.atender(sesion, "le pago el miércoles").tarjeta
    llamadas = len(agente.recibido)
    r = orq.atender(sesion, boton=Boton.cancelar)
    assert r.mensajes == [TEXTOS["tope"]] and r.cerrada and sesion.motivo_cierre == "tope"
    assert len(agente.recibido) == llamadas


def test_abuso_no_cuenta_turno_y_llega_como_evento(repo, ahora):
    agente = ModeloGuionado()
    orq = _orq(repo, ahora, agente, moderador=ModeloGuionado("1", "0"))
    sesion = orq.iniciar(CID, "CV-1")
    orq.atender(sesion, "insulto")
    assert sesion.turno == 0 and agente.recibido == []
    orq.atender(sesion, "perdón")
    assert "strike 1 de 3" in agente.todo_lo_recibido()


def test_tope_de_pasos_insistente_responde_el_texto_fijo(repo, ahora):
    agente = ModeloGuionado(*[("consultar_saldo", {})] * 20)
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    r = orq.atender(sesion, "¿cuánto debo?")
    assert r.mensajes == [TEXTOS["pasos"]] and not r.cerrada


def test_verificacion_vencida_pide_de_nuevo_los_digitos(repo, ahora):
    reloj = {"t": ahora()}
    agente = ModeloGuionado("¿Me da los últimos cuatro dígitos de su cédula?", "Gracias.", "Hola.")
    orq = _orq(repo, lambda: reloj["t"], agente)
    sesion = orq.iniciar(CID, "CV-1")
    orq.atender(sesion, "hola")
    orq.atender(sesion, _digitos(repo))
    assert sesion.verificada and sesion.verificada_en == reloj["t"]
    reloj["t"] += timedelta(hours=12)
    orq.atender(sesion, "sigo aquí")
    assert not sesion.verificada
    assert "La verificación venció" in agente.todo_lo_recibido()


def test_tope_de_pasos_tras_un_cierre_usa_el_texto_del_cierre(repo, ahora):
    escalar = ("escalar_a_humano", {"motivo": "pide_humano", "resumen": "x"})
    agente = ModeloGuionado(escalar, *[("consultar_saldo", {})] * 20)
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    r = orq.atender(sesion, "quiero un asesor")
    assert r.cerrada and r.mensajes == [TEXTOS["handoff"]]


def _verificada(repo, ahora, agente):
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    return orq, sesion


def test_confirmar_promesa_reusa_el_link_ya_enviado(repo, ahora):
    agente = ModeloGuionado(
        ("generar_link_pago", {}),
        "Pague aquí: {{link_pago}}",
        ("registrar_promesa_pago", {"fecha": "mañana"}),
    )
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "¿cómo pago?")
    orq.atender(sesion, "mejor mañana")
    r = orq.atender(sesion, boton=Boton.confirmar)
    assert r.mensajes[0].endswith(
        "Ese día puede pagar con el link que le envié. ¿Le ayudo con algo más?"
    )
    assert len(repo.links) == 1


def test_confirmar_oferta_envia_el_link_sin_llamar_al_llm(repo, ahora):
    agente = ModeloGuionado(("aceptar_oferta", {"oferta_id": "OF-102"}))
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "quiero la prórroga")
    r = orq.atender(sesion, boton=Boton.confirmar)
    assert r.mensajes == [
        "Listo, Itzel. Quedó aceptada su oferta. Puede pagar $76.40, hasta el miércoles 11 de "
        f"noviembre, con este link: {repo.links[-1].url}. ¿Le ayudo con algo más?"
    ]
    assert len(repo.aceptaciones) == 1 and len(agente.recibido) == 1


def _oferta_confirmada(repo, ahora, oferta_id, monto=None):
    """Cliente dificultad_temporal que acepta `oferta_id` y toca Confirmar; luego escribe."""
    agente = ModeloGuionado(("aceptar_oferta", {"oferta_id": oferta_id}), "De nada.")
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID_DIFICULTAD, "CV-1")
    sesion.verificada = True
    orq.atender(sesion, "quiero esa")
    if monto is not None:
        sesion.tarjeta = sesion.tarjeta.model_copy(update={"monto": Decimal(monto)})
    r = orq.atender(sesion, boton=Boton.confirmar)
    return orq, sesion, agente, r


def test_confirmar_cambio_de_corte_incluye_el_link_del_saldo(repo, ahora):
    orq, sesion, agente, r = _oferta_confirmada(repo, ahora, "OF-120")
    url = repo.links[-1].url
    assert r.mensajes == [
        "Listo, Rodrigo. Quedó aceptado el cambio de fecha de corte. Su saldo vencido sigue "
        f"pendiente: puede pagar $23.49, con este link: {url}. ¿Le ayudo con algo más?"
    ]
    assert url not in sesion.transcripcion[-1][1] and "{{link_pago}}" in sesion.transcripcion[-1][1]
    orq.atender(sesion, "gracias")
    assert "la confirmación y el link de pago" in agente.todo_lo_recibido()


def test_confirmar_plan_de_cuotas_cobra_la_primera_cuota(repo, ahora):
    _, _, _, r = _oferta_confirmada(repo, ahora, "OF-110")
    assert "Puede pagar la primera cuota, $11.74, con este link: " in r.mensajes[0]


def test_confirmar_con_monto_cero_no_genera_link(repo, ahora):
    orq, sesion, agente, r = _oferta_confirmada(repo, ahora, "OF-120", monto="0")
    assert r.mensajes == [
        "Listo, Rodrigo. Quedó aceptado el cambio de fecha de corte. ¿Le ayudo con algo más?"
    ]
    assert repo.links == [] and "link_pago" not in sesion.valores
    orq.atender(sesion, "gracias")
    recibido = agente.todo_lo_recibido()
    assert (
        "ya le envió la confirmación: no lo repitas" in recibido and "link de pago" not in recibido
    )


def test_confirmar_promesa_con_link_reusado_no_lo_anuncia(repo, ahora):
    agente = ModeloGuionado(
        ("generar_link_pago", {}),
        "Pague aquí: {{link_pago}}",
        ("registrar_promesa_pago", {"fecha": "mañana"}),
        "De nada.",
    )
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "¿cómo pago?")
    orq.atender(sesion, "mejor mañana")
    orq.atender(sesion, boton=Boton.confirmar)
    assert "{{link_pago}}" not in sesion.transcripcion[-1][1]
    orq.atender(sesion, "gracias")
    recibido = agente.todo_lo_recibido()
    assert "ya le envió la confirmación: no lo repitas" in recibido
    assert "la confirmación y el link de pago" not in recibido


def test_texto_con_tarjeta_pendiente_avisa_al_agente(repo, ahora):
    agente = ModeloGuionado(("registrar_promesa_pago", {"fecha": "mañana"}), "Elija en la tarjeta.")
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "le pago mañana")
    r = orq.atender(sesion, "¿y si mejor el viernes?")
    assert "sin responder la tarjeta pendiente (promesa de pago)" in agente.todo_lo_recibido()
    assert sesion.tarjeta is not None and r.mensajes == ["Elija en la tarjeta."]


def test_pedir_confirmacion_en_texto_se_corrige_con_la_tarjeta(repo, ahora):
    agente = ModeloGuionado(
        "¿Confirma que le registro la promesa para mañana?",
        ("registrar_promesa_pago", {"fecha": "mañana"}),
    )
    orq, sesion = _verificada(repo, ahora, agente)
    r = orq.atender(sesion, "le pago mañana")
    assert r.mensajes == [] and r.tarjeta is not None
    assert "No pidas confirmación en texto" in agente.todo_lo_recibido()
    historial = json.dumps(sesion.historial, ensure_ascii=False)
    assert "¿Confirma" not in historial and "No pidas confirmación" not in historial


def test_si_la_correccion_falla_se_envia_la_respuesta_original(repo, ahora):
    agente = ModeloGuionado(
        "¿Procedo con el registro?", "Son 50 dólares."
    )  # el reintento es inválido
    orq, sesion = _verificada(repo, ahora, agente)
    r = orq.atender(sesion, "sí")
    assert r.mensajes == ["¿Procedo con el registro?"] and not r.cerrada
    assert "dólares" not in json.dumps(sesion.historial, ensure_ascii=False)


def test_pedir_los_cuatro_digitos_no_cuenta_como_confirmacion(repo, ahora):
    agente = ModeloGuionado("¿Me confirma los últimos cuatro dígitos de su cédula?")
    orq = _orq(repo, ahora, agente)
    r = orq.atender(orq.iniciar(CID, "CV-1"), "hola")
    assert len(agente.recibido) == 1 and "cuatro dígitos" in r.mensajes[0]


@pytest.mark.parametrize(
    "texto",
    ["¿Ya registró su pago?", "¿Desea proceder con el link?", "¿Le sirve esta opción?"],
)
def test_preguntas_legitimas_no_se_corrigen(repo, ahora, texto):
    agente = ModeloGuionado(texto)
    orq, sesion = _verificada(repo, ahora, agente)
    assert orq.atender(sesion, "hola").mensajes == [texto] and len(agente.recibido) == 1


def test_respuesta_vacia_sin_tarjeta_se_reintenta(repo, ahora):
    agente = ModeloGuionado("", "Hola, ¿en qué le ayudo?")
    orq, sesion = _verificada(repo, ahora, agente)
    assert orq.atender(sesion, "hola").mensajes == ["Hola, ¿en qué le ayudo?"]


def test_tarjeta_y_escalamiento_en_el_mismo_lote_cierran_con_el_texto_fijo(repo, ahora):
    agente = ModeloGuionado(
        ("escalar_a_humano", {"motivo": "pide_humano", "resumen": "x"}),
        ("registrar_promesa_pago", {"fecha": "mañana"}),
    )
    orq, sesion = _verificada(repo, ahora, agente)
    r = orq.atender(sesion, "le pago mañana, pero quiero un asesor")
    assert r.cerrada and r.tarjeta is None and r.mensajes == [TEXTOS["handoff"]]
    assert repo.handoffs[0].motivo == "pide_humano"  # no un fallo nuestro


def test_el_historial_no_guarda_las_cifras_de_la_tarjeta(repo, ahora):
    agente = ModeloGuionado(("registrar_promesa_pago", {"fecha": "mañana"}))
    orq, sesion = _verificada(repo, ahora, agente)
    r = orq.atender(sesion, "le pago mañana")
    assert "$" in r.tarjeta.texto
    final = sesion.historial[-1]
    assert final["role"] == "assistant" and "$" not in json.dumps(final, ensure_ascii=False)
    assert "tarjeta enviada: promesa de pago" in final["content"][0]["text"]


def test_tarjeta_de_oferta_cierra_el_turno_sin_cifras_en_el_historial(repo, ahora):
    agente = ModeloGuionado(("aceptar_oferta", {"oferta_id": "OF-102"}))
    orq, sesion = _verificada(repo, ahora, agente)
    r = orq.atender(sesion, "quiero la prórroga")
    assert r.mensajes == [] and r.tarjeta.oferta_id == "OF-102" and len(agente.recibido) == 1
    assert "tarjeta enviada: oferta OF-102" in sesion.historial[-1]["content"][0]["text"]
    assert sesion.transcripcion[-1] == ("agente", f"[tarjeta] {r.tarjeta.texto}")


def test_reintento_por_salida_invalida_puede_terminar_con_tarjeta(repo, ahora):
    agente = ModeloGuionado("Son 50 dólares.", ("registrar_promesa_pago", {"fecha": "mañana"}))
    orq, sesion = _verificada(repo, ahora, agente)
    r = orq.atender(sesion, "le pago mañana")
    assert r.mensajes == [] and r.tarjeta is not None and not r.cerrada
    assert "dólares" not in json.dumps(sesion.historial, ensure_ascii=False)


def _pago_en_transito(repo, monto):
    factura = estado_cuenta(repo, CID).facturas_vencidas[0]
    repo._pagos.append(
        Pago(
            pago_id="PG-H3",
            factura_id=factura.factura_id,
            customer_id=CID,
            fecha=datetime.combine(repo.fecha_referencia, datetime.min.time()).astimezone(),
            monto=monto,
            canal="app",
            estado="en_transito",
        )
    )


def test_un_pago_entre_mensajes_actualiza_cifras_y_anula_la_tarjeta(repo, ahora):
    agente = ModeloGuionado(
        ("consultar_saldo", {}),
        ("registrar_promesa_pago", {"fecha": "mañana"}),
        "Veo su pago.",
    )
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "le pago mañana")
    assert sesion.tarjeta is not None and sesion.valores["saldo_tras_transito"] == "$76.40"
    _pago_en_transito(repo, "76.40")
    orq.atender(sesion, "ya pagué")
    assert sesion.tarjeta is None and sesion.valores["saldo_tras_transito"] == "$0.00"
    recibido = agente.todo_lo_recibido()
    assert "La cuenta del cliente cambió" in recibido and "Se anuló la tarjeta" in recibido


def test_una_oferta_que_deja_de_aplicar_se_retira(repo, ahora):
    agente = ModeloGuionado(("aceptar_oferta", {"oferta_id": "OF-102"}), "Entendido.")
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "quiero la prórroga")
    _pago_en_transito(repo, "76.40")
    r = orq.atender(sesion, boton=Boton.confirmar)  # llega tarde: ya no hay nada que aceptar
    assert r.mensajes == [TEXTOS["sin_tarjeta"]] and repo.aceptaciones == []
    assert "OF-102" not in sesion.condiciones
    assert not any(k.startswith("of_102.") for k in sesion.valores)
    assert any("Ya no aplican: OF-102" in e for e in sesion.eventos)  # llega en el próximo turno


def test_sin_cambios_en_la_cuenta_no_hay_aviso(repo, ahora):
    agente = ModeloGuionado(("consultar_saldo", {}), "Su saldo es {{saldo_vencido}}.", "Ok.")
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "¿cuánto debo?")
    orq.atender(sesion, "ok")
    assert "La cuenta del cliente cambió" not in agente.todo_lo_recibido()


def test_la_oferta_aceptada_no_se_recalcula_tras_el_pago(repo, ahora):
    agente = ModeloGuionado(
        ("aceptar_oferta", {"oferta_id": "OF-102"}), ("generar_link_pago", {}), "Listo.", "Ok."
    )
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "quiero la prórroga")
    orq.atender(sesion, boton=Boton.confirmar)
    cifras = {k: v for k, v in sesion.valores.items() if k.startswith("of_102.")}
    _pago_en_transito(repo, "76.40")
    orq.atender(sesion, "ya pagué")
    assert "OF-102" in sesion.condiciones
    assert {k: v for k, v in sesion.valores.items() if k.startswith("of_102.")} == cifras
    assert "Ya no aplican" not in agente.todo_lo_recibido()


def test_boton_tras_vencer_la_verificacion_no_registra(repo, ahora):
    reloj = {"t": ahora()}
    agente = ModeloGuionado(("registrar_promesa_pago", {"fecha": "mañana"}))
    orq = _orq(repo, lambda: reloj["t"], agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada, sesion.verificada_en = True, reloj["t"]
    orq.atender(sesion, "le pago mañana")
    reloj["t"] += timedelta(hours=12)
    r = orq.atender(sesion, boton=Boton.confirmar)
    assert r.mensajes == [TEXTOS["sin_tarjeta"]] and repo.promesas == []
    assert not sesion.condiciones and not sesion.valores


def test_la_tarjeta_sigue_si_su_monto_no_cambio(repo, ahora):
    agente = ModeloGuionado(
        ("aceptar_oferta", {"oferta_id": "OF-102"}),
        ("consultar_saldo", {}),
        ("registrar_promesa_pago", {"fecha": "mañana"}),
        "Veo su abono.",
    )
    orq, sesion = _verificada(repo, ahora, agente)
    orq.atender(sesion, "quiero la prórroga")
    orq.atender(sesion, boton=Boton.confirmar)
    orq.atender(sesion, "le pago mañana")
    tarjeta, saldo = sesion.tarjeta, sesion.valores["saldo_tras_transito"]
    assert tarjeta is not None and tarjeta.monto == sesion.oferta_aceptada.primer_pago
    _pago_en_transito(repo, "10.00")
    orq.atender(sesion, "aboné algo")
    assert sesion.valores["saldo_tras_transito"] != saldo and sesion.tarjeta == tarjeta
    recibido = agente.todo_lo_recibido()
    assert "La cuenta del cliente cambió" in recibido and "Se anuló la tarjeta" not in recibido
