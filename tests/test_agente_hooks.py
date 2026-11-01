import json

import pytest
from conftest import ModeloGuionado
from strands import Agent

from agil.agente.hooks import VERIFICACION_PENDIENTE, Controles
from agil.agente.sesion import Sesion
from agil.agente.tools import SENSIBLES, crear_tools
from agil.dominio.modelos import Cola, Segmento


def _sesion(**cambios):
    datos = {
        "conversacion_id": "CV-T",
        "customer_id": "CL-1140215",
        "segmento": Segmento.mora_avanzada,
        "cola": Cola.especializada,
        "max_turnos": 10,
        "max_caracteres": 400,
    }
    return Sesion(**(datos | cambios))


def _agente(repo, sesion, ahora, modelo, max_pasos=6):
    return Agent(
        model=modelo,
        tools=crear_tools(repo, sesion, ahora),
        hooks=[Controles(repo, sesion, max_pasos)],
        callback_handler=None,
    )


def _resultados_de_tools(modelo) -> list[str]:
    """Textos de los toolResult que el modelo recibió en su última llamada."""
    _, mensajes = modelo.recibido[-1]
    return [
        json.dumps(b["toolResult"], ensure_ascii=False)
        for m in mensajes
        for b in m["content"]
        if "toolResult" in b
    ]


def test_tool_sensible_sin_verificar_se_cancela_con_motivo(repo, ahora):
    sesion = _sesion()
    modelo = ModeloGuionado(("consultar_saldo", {}), "Necesito sus cuatro dígitos.")
    _agente(repo, sesion, ahora, modelo)("¿cuánto debo?")
    assert any(VERIFICACION_PENDIENTE in r for r in _resultados_de_tools(modelo))
    assert sesion.cedula_pedida and "saldo_vencido" not in sesion.valores


def test_tool_no_sensible_sin_verificar_corre(repo, ahora):
    sesion = _sesion()
    modelo = ModeloGuionado(("escalar_a_humano", {"motivo": "pide_humano", "resumen": "x"}), "Ok.")
    _agente(repo, sesion, ahora, modelo)("quiero un asesor")
    assert len(repo.handoffs) == 1 and sesion.cerrada


def test_verificacion_bloqueada_tras_tres_fallos(repo, ahora):
    sesion = _sesion(intentos_cedula=3)
    modelo = ModeloGuionado(("consultar_saldo", {}), "Le paso con un asesor.")
    _agente(repo, sesion, ahora, modelo)("¿cuánto debo?")
    assert any("bloqueada" in r for r in _resultados_de_tools(modelo))
    assert not sesion.cedula_pedida


def test_verificado_la_tool_corre(repo, ahora):
    sesion = _sesion(verificada=True)
    modelo = ModeloGuionado(("consultar_saldo", {}), "Su saldo es {{saldo_vencido}}.")
    _agente(repo, sesion, ahora, modelo)("¿cuánto debo?")
    assert sesion.valores["saldo_vencido"] == "$427.89"


def test_oferta_invalida_se_cancela_con_el_motivo_del_motor(repo, ahora):
    sesion = _sesion(verificada=True)
    modelo = ModeloGuionado(
        ("aceptar_oferta", {"oferta_id": "OF-141"}),  # requiere aprobación humana
        ("aceptar_oferta", {"oferta_id": "OF-999"}),
        "Le paso con un asesor.",
    )
    _agente(repo, sesion, ahora, modelo)("quiero el 35")
    resultados = _resultados_de_tools(modelo)
    assert any("aprobación humana" in r for r in resultados)
    assert any("no existe" in r for r in resultados)
    assert sesion.tarjeta is None


def test_promesa_con_oferta_invalida_se_cancela(repo, ahora):
    sesion = _sesion(verificada=True)
    modelo = ModeloGuionado(
        ("registrar_promesa_pago", {"fecha": "2026-11-08", "oferta_id": "OF-102"}), "Ok."
    )
    _agente(repo, sesion, ahora, modelo)("pago el domingo")
    assert any("segmento" in r for r in _resultados_de_tools(modelo))
    assert sesion.tarjeta is None


def test_tope_de_pasos_por_turno(repo, ahora):
    sesion = _sesion(verificada=True)
    modelo = ModeloGuionado(*[("consultar_saldo", {})] * 3, "Listo.")
    _agente(repo, sesion, ahora, modelo, max_pasos=2)("¿cuánto debo?")
    assert any("Límite de pasos" in r for r in _resultados_de_tools(modelo))


def test_contexto_se_inyecta_antes_del_mensaje_del_cliente(repo, ahora):
    sesion = _sesion(contexto=["[contexto] Turno 2 de 10."])
    modelo = ModeloGuionado("Hola.")
    _agente(repo, sesion, ahora, modelo)("Cliente: hola")
    _, mensajes = modelo.recibido[0]
    textos = [b["text"] for b in mensajes[-1]["content"]]
    assert textos == ["[contexto] Turno 2 de 10.", "Cliente: hola"]


def test_contexto_no_queda_en_el_historial(repo, ahora):
    sesion = _sesion(contexto=["[contexto] Turno 2 de 10."])
    agente = _agente(repo, sesion, ahora, ModeloGuionado("Hola."))
    agente("Cliente: hola")
    assert "Turno 2" not in str(agente.messages) and "Cliente: hola" in str(agente.messages)


def test_oferta_id_vacio_tambien_se_valida(repo, ahora):
    sesion = _sesion(verificada=True)
    modelo = ModeloGuionado(("aceptar_oferta", {"oferta_id": ""}), "Ok.")
    _agente(repo, sesion, ahora, modelo)("esa")
    assert any("no existe" in r for r in _resultados_de_tools(modelo))


_ARGS_SENSIBLES = {
    "consultar_saldo": {},
    "consultar_ofertas_elegibles": {},
    "aceptar_oferta": {"oferta_id": "OF-140"},
    "registrar_promesa_pago": {"fecha": "2026-11-08"},
    "generar_link_pago": {},
    "guardar_nota": {"texto": "x", "flags": []},
    "registrar_feedback_cliente": {"texto": "x", "etiquetas": []},
}


def test_lista_de_sensibles_es_la_del_diseno():
    assert set(_ARGS_SENSIBLES) == SENSIBLES


@pytest.mark.parametrize("nombre", sorted(_ARGS_SENSIBLES))
def test_cada_tool_sensible_se_cancela_sin_verificar(repo, ahora, nombre):
    sesion = _sesion()
    notas = len(repo.notas("CL-1140215"))
    modelo = ModeloGuionado((nombre, _ARGS_SENSIBLES[nombre]), "Necesito sus cuatro dígitos.")
    _agente(repo, sesion, ahora, modelo)("hola")
    assert any(VERIFICACION_PENDIENTE in r for r in _resultados_de_tools(modelo))
    assert sesion.tarjeta is None and sesion.valores == {} and sesion.escrituras == set()
    assert repo.links == [] and repo.feedbacks == [] and len(repo.notas("CL-1140215")) == notas


def test_contador_de_pasos_se_reinicia_cada_turno(repo, ahora):
    sesion = _sesion(verificada=True)
    modelo = ModeloGuionado(("consultar_saldo", {}), "Uno.", ("consultar_saldo", {}), "Dos.")
    agente = _agente(repo, sesion, ahora, modelo, max_pasos=1)
    agente("¿cuánto debo?")
    agente("¿y ahora?")
    assert not any("Límite de pasos" in r for r in _resultados_de_tools(modelo))


def test_sin_contexto_el_mensaje_queda_igual(repo, ahora):
    modelo = ModeloGuionado("Hola.")
    _agente(repo, _sesion(), ahora, modelo)("Cliente: hola")
    _, mensajes = modelo.recibido[0]
    assert [b["text"] for b in mensajes[-1]["content"]] == ["Cliente: hola"]
