import json

import pytest

from agil.dominio.intenciones import Boton, pide_no_contacto
from agil.dominio.repositorio.memoria import DATOS_MOCK


@pytest.mark.parametrize(
    "mensaje",
    [
        "STOP",
        "stop.",
        "BAJA",
        "NO ME ESCRIBAN MAS",
        "No me escriban más, por favor",
        "no me contacten",
        "no me vuelvan a escribir",
        "No nos contacten",
        "stop porfa",
        "no quiero que me escriban",
        "no quiero recibir más mensajes",
        "dejen de escribirme",
        "Dejen de contactarme!!",
        "borren mi número",
        "no me molesten más",
        "DÉJEN DE ESCRIBIRME",
        "stop por favor",
        "Baja, gracias",
        "no quiero que me sigan escribiendo",
        "Por favor, no me escriban nunca más.",
        "No me escriban más. Gracias.",
        "No me sigan escribiendo",
        "No me escriban nunca",
        "Dejen de molestarme",
        "Señores, les pido que no me escriban más",
        # Una por alternativa de _EXPLICITAS/_CORTESIA no cubierta arriba.
        "no me escribas",
        "no me escriba más",
        "no me contactes",
        "No me contacte",
        "no me manden más mensajes",
        "no me envíen mensajes",
        "no me vuelvan a contactar",
        "no me sigan contactando",
        "no me sigan mandando mensajes",
        "no quiero que me contacten",
        "no quiero que me sigan contactando",
        "no quiero que me sigan mandando mensajes",
        "no quiero más mensajes",
        "dejen de mandarme mensajes",
        "dejen de enviarme mensajes",
        "eliminen mi número",
        "saquen mi número",
        "ya no me escriban",
        "le pido que no me contacte",
    ],
)
def test_frases_explicitas(mensaje):
    assert pide_no_contacto(mensaje)


@pytest.mark.parametrize(
    "mensaje",
    [
        "ahora no puedo hablar",
        "estoy manejando, después le escribo",
        "ya dejen de escribirme todos los dias",
        "me baja la señal",
        "quiero darme de baja del plan",
        "no me presionen mucho porfa",
        "stop motion",
        "no me llega la factura",
        "baja la tarifa",
        "no me escriba ahora, estoy ocupado",
        "no me escriban hoy",
        "yo nunca dije que no me escriban",
        "dejen de escribirme tanto",
        "stop gracias por la info",
        "no me escriban por whatsapp, llamenme",
        "no me escriban, ya pague",
        "Hoy no me escriban.",
        "Mañana pago. Por whatsapp no me escriban",
        "Si no pago, no me escriban",
        "¿Quién dijo que no me escriban?",
        "no dije que me dejen de escribir, dije que no me contacten",
        "No me escriban. Hasta el lunes",
        "no me escriban\nhoy estoy ocupado",
        "No me escriban!! Ya pagué",
        "Stop. Ya pagué ayer",
        "No me escriban por favor. Llámenme al fijo",
        "¿no me escriban más",
        # Frase explícita con más texto: va al agente (D13), que usa derivar_solicitud_contacto.
        "NO ME ESCRIBAN MAS. yo se que debo y voy a pagar cuando pueda",
        "no dije que pagaria. no me escriban mas",
    ],
)
def test_no_detecta_ambiguos(mensaje):
    assert not pide_no_contacto(mensaje)


def test_conversaciones_ejemplo_sin_falsos_positivos():
    """Ningún mensaje de cliente de los ejemplos pausa WhatsApp salvo los que el mock marca."""
    conversaciones = json.loads(
        (DATOS_MOCK / "conversaciones_ejemplo.json").read_text(encoding="utf-8")
    )
    clientes = 0
    for c in conversaciones:
        mensajes = c["mensajes"]
        for i, m in enumerate(mensajes):
            if m["rol"] != "cliente":
                continue
            clientes += 1
            siguiente = mensajes[i + 1]["texto"] if i + 1 < len(mensajes) else ""
            if pide_no_contacto(m["texto"]):
                assert "no contacto detectada" in siguiente, m["texto"]
    assert clientes > 0


def test_botones_ids_estables():
    assert Boton.confirmar == "btn_confirmar"
    assert Boton.cancelar == "btn_cancelar"


@pytest.mark.parametrize("mensaje", ["stop?", "¿Me escriben mañana? No me escriban más."])
def test_preguntas_van_al_agente(mensaje):
    """Un mensaje con pregunta nunca lo resuelve el router."""
    assert not pide_no_contacto(mensaje)


@pytest.mark.parametrize("mensaje", ["", "   ", "Gracias.", "Por favor!! Gracias", "..."])
def test_vacio_o_solo_cortesia_no_pausa(mensaje):
    """Sin ninguna oración explícita no hay no-contacto."""
    assert not pide_no_contacto(mensaje)
