import json
import re

import pytest
from conftest import ModeloGuionado

from agil.agente.auxiliares import (
    Momento,
    clasificar_momento,
    es_abusivo,
    resumir,
    tarjeta_estrategia,
)
from agil.agente.perfiles import PROMPTS, cargar_perfil, prompt_sistema
from agil.dominio.harness.validador import validar_salida
from agil.dominio.modelos import FlagMemoria, Segmento

CONTACTABLES = [s for s in Segmento if s is not Segmento.excluido]
LINEAS = [("agente", "Hola"), ("cliente", "ya pagué ayer")]


@pytest.mark.parametrize("segmento", CONTACTABLES)
def test_cada_segmento_contactable_tiene_perfil(segmento):
    perfil = cargar_perfil(segmento)
    assert perfil.max_turnos > 3 and perfil.max_caracteres == 400
    assert "placeholder" in perfil.prompt


@pytest.mark.parametrize("segmento", [Segmento.reincidente, Segmento.valioso_churn])
def test_perfiles_cortos_lo_dicen(segmento):
    assert "a propósito" in cargar_perfil(segmento).prompt  # D33


def test_prompt_de_sistema_sin_datos_de_la_cuenta(repo, ahora):
    cliente = repo.cliente("CL-1140215")
    texto = prompt_sistema(cargar_perfil(Segmento.mora_avanzada), cliente, ahora())
    assert "Euclides" in texto and cliente.nombre not in texto
    assert cliente.cedula not in texto and "427" not in texto
    assert "viernes 6 de noviembre de 2026" in texto
    assert '"buenas tardes"' in texto


@pytest.mark.parametrize("segmento", CONTACTABLES)
def test_prompt_de_sistema_se_presenta_como_asistente_de_liberty(repo, ahora, segmento):
    texto = prompt_sistema(cargar_perfil(segmento), repo.cliente("CL-1140215"), ahora())
    assert "asistente virtual de Liberty" in texto  # D39


def test_toda_plantilla_dice_que_escribe_liberty():
    plantillas = json.loads((PROMPTS / "plantillas.json").read_text(encoding="utf-8"))
    assert set(plantillas) == {s.value for s in CONTACTABLES}
    for p in plantillas.values():
        assert "le escribe Liberty" in p["texto"], p["id"]  # D39
    assert len({p["id"] for p in plantillas.values()}) == len(plantillas)


def test_cada_momento_tiene_tarjeta_menos_otro():
    tarjetas = json.loads((PROMPTS / "estrategias.json").read_text(encoding="utf-8"))
    assert set(tarjetas) == {m.value for m in Momento} - {"otro"}
    assert tarjeta_estrategia(Momento.otro) is None


def test_prompt_del_estratega_lista_todo_el_catalogo():
    lista = re.findall(r"^- (\w+)", (PROMPTS / "estratega.md").read_text(encoding="utf-8"), re.M)
    assert lista == [m.value for m in Momento]


def test_tarjetas_pasan_el_validador():
    """Si el agente copiara una tarjeta, no traería cifras."""
    for texto in json.loads((PROMPTS / "estrategias.json").read_text(encoding="utf-8")).values():
        assert validar_salida(texto, set(), 400).ok, texto


@pytest.mark.parametrize(
    ("salida", "esperado"),
    [
        ("pago_reciente", Momento.pago_reciente),
        ("  Enojo.", Momento.enojo),
        ("Etiqueta: duda", Momento.duda),
        ("Conforme.", Momento.conforme),
        ("otro, conforme", Momento.conforme),
        ("evasión", Momento.evasion),
        ("no sé", None),
        ("", None),
    ],
)
def test_clasificar_momento(salida, esperado):
    assert clasificar_momento(ModeloGuionado(salida), LINEAS) is esperado


class _Caido(ModeloGuionado):
    async def stream(self, *args, **kwargs):
        raise RuntimeError("sin red")
        yield


def test_auxiliares_caidos_no_bloquean():
    assert clasificar_momento(_Caido(), LINEAS) is None
    assert es_abusivo(_Caido(), "hola") is False
    assert resumir(_Caido(), LINEAS) is None


@pytest.mark.parametrize(("salida", "esperado"), [("1", True), ("0", False)])
def test_es_abusivo(salida, esperado):
    assert es_abusivo(ModeloGuionado(salida), "mensaje") is esperado


def test_resumir_descarta_flags_fuera_del_catalogo():
    salida = (
        '```json\n{"texto": "Dice que pagó.", "flags": ["promesa_incumplida", "inventado"]}\n```'
    )
    r = resumir(ModeloGuionado(salida), LINEAS)
    assert r.texto == "Dice que pagó." and r.flags == [FlagMemoria.promesa_incumplida]


def test_resumir_invalido():
    assert resumir(ModeloGuionado("no es json"), LINEAS) is None


def test_estratega_solo_ve_las_ultimas_lineas():
    modelo = ModeloGuionado("duda")
    lineas = [("cliente", f"mensaje {i}") for i in range(10)]
    clasificar_momento(modelo, lineas)
    recibido = modelo.todo_lo_recibido()
    assert "mensaje 9" in recibido and "mensaje 3" not in recibido


@pytest.mark.parametrize(
    ("hora", "minuto", "saludo"),
    [
        (7, 0, "buenos días"),
        (11, 59, "buenos días"),
        (12, 0, "buenas tardes"),
        (18, 59, "buenas tardes"),
        (19, 0, "buenas noches"),
        (22, 30, "buenas noches"),
    ],
)
def test_saludo_segun_la_hora(repo, ahora, hora, minuto, saludo):
    momento = ahora().replace(hour=hora, minute=minuto)
    texto = prompt_sistema(cargar_perfil(Segmento.olvidadizo), repo.cliente("CL-1140215"), momento)
    assert f'"{saludo}"' in texto and f"{hora:02d}:{minuto:02d}" in texto


def test_perfiles_json_solo_contactables():
    config = json.loads((PROMPTS / "perfiles.json").read_text(encoding="utf-8"))
    assert set(config["segmentos"]) == {s.value for s in CONTACTABLES}


@pytest.mark.parametrize("archivo", ["base.md", *(f"segmentos/{s.value}.md" for s in CONTACTABLES)])
def test_prompts_sin_cifras_literales(archivo):
    """El prompt de sistema no pasa el validador, pero no debe dar cifras, montos ni URLs que el
    LLM pueda copiar (las palabras sueltas como "dos meses" describen el segmento y se toleran)."""
    # Las referencias a decisiones ("D33") no son cifras para el cliente.
    texto = re.sub(r"\bD\d+\b", "", (PROMPTS / archivo).read_text(encoding="utf-8"))
    assert not re.search(r"\d|\$|%|B/\.|https?://|www\.", texto), archivo


def test_resumir_deduplica_flags_repetidos():
    salida = json.dumps(
        {
            "texto": "Cobra en quincena.",
            "flags": ["fecha_pago_desfasada", "dificultad_economica", "fecha_pago_desfasada"],
        }
    )
    r = resumir(ModeloGuionado(salida), LINEAS)
    assert r.flags == [FlagMemoria.fecha_pago_desfasada, FlagMemoria.dificultad_economica]


def test_resumir_sin_flags_o_sin_texto():
    assert resumir(ModeloGuionado('{"texto": "Nada."}'), LINEAS).flags == []
    assert resumir(ModeloGuionado('{"flags": []}'), LINEAS) is None


@pytest.mark.parametrize("salida", ["duda o enojo", "enojo o duda"])
def test_estratega_con_dos_etiquetas_gana_el_orden_del_catalogo(salida):
    """Determinista: ante ambigüedad decide el orden de Momento, no el del texto."""
    assert clasificar_momento(ModeloGuionado(salida), LINEAS) is Momento.duda


def test_estratega_no_confunde_etiquetas_dentro_de_palabras():
    assert clasificar_momento(ModeloGuionado("dudas_varias"), LINEAS) is None


def test_moderacion_recibe_el_mensaje_y_su_politica():
    modelo = ModeloGuionado("0")
    es_abusivo(modelo, "esta empresa es lo peor")
    sistema, mensajes = modelo.recibido[0]
    assert "Responde solo con 1 o 0" in sistema
    assert "esta empresa es lo peor" in json.dumps(mensajes, ensure_ascii=False)
