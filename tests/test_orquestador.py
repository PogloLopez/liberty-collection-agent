import json
from datetime import timedelta

import pytest
from conftest import ModeloGuionado

from agil.agente.config import Modelos
from agil.agente.orquestador import TEXTOS, Orquestador
from agil.agente.sesion import Sesion
from agil.dominio.harness.identidad import ultimos_cuatro
from agil.dominio.harness.intenciones import Boton

CID = "CL-1171492"  # olvidadizo, con prórroga de 5 días


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
        "Confirme con el botón, por favor.",
        "Listo, quedó registrada para el {{fecha_promesa}}.",
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    r1 = orq.atender(sesion, "le pago el miércoles")
    assert r1.tarjeta.texto == "Promesa de pago de $76.40 para el miércoles 11 de noviembre."
    assert repo.promesas == []
    r2 = orq.atender(sesion, boton=Boton.confirmar)
    assert r2.mensajes == ["Listo, quedó registrada para el miércoles 11 de noviembre."]
    assert len(repo.promesas) == 1 and str(repo.promesas[0].monto) == "76.40"
    assert "confirmó la tarjeta" in agente.todo_lo_recibido()
    assert orq.atender(sesion, boton=Boton.confirmar).mensajes == [TEXTOS["sin_tarjeta"]]
    assert len(repo.promesas) == 1


def test_boton_cancelar_no_registra(repo, ahora):
    agente = ModeloGuionado(("aceptar_oferta", {"oferta_id": "OF-102"}), "Confirme.", "Entendido.")
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

    agente2 = ModeloGuionado("Listo, quedó para el {{fecha_promesa}}.")
    r = _orq(repo, ahora, agente2).atender(reanudada, boton=Boton.confirmar)
    assert r.mensajes == ["Listo, quedó para el miércoles 11 de noviembre."]
    assert len(repo.promesas) == 1
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


def test_tope_cuenta_tambien_los_botones(repo, ahora):
    agente = ModeloGuionado(
        ("registrar_promesa_pago", {"fecha": "2026-11-11"}), "Confirme con el botón."
    )
    orq = _orq(repo, ahora, agente)
    sesion = orq.iniciar(CID, "CV-1")
    sesion.verificada = True
    sesion.turno = sesion.max_turnos - 1
    assert orq.atender(sesion, "le pago el miércoles").tarjeta
    llamadas = len(agente.recibido)
    r = orq.atender(sesion, boton=Boton.confirmar)
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
