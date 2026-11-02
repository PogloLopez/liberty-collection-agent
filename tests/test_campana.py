import json
import re

import pytest
from conftest import ModeloGuionado

from agil.agente.config import Modelos
from agil.agente.orquestador import Orquestador
from agil.agente.perfiles import PROMPTS
from agil.app.campana import plantilla, que_sean_las_9

_PLANTILLAS = json.loads((PROMPTS / "plantillas.json").read_text(encoding="utf-8"))
DEMO = ["CL-1171492", "CL-1152549", "CL-1140215", "CL-1191572", "CL-1100708"]


@pytest.fixture
def orq(repo, ahora):
    return Orquestador(repo, Modelos(agente=ModeloGuionado()), ahora)


@pytest.mark.parametrize("cid", DEMO)
def test_envia_la_plantilla_del_segmento_y_registra_el_contacto(orq, repo, cid):
    envio = que_sean_las_9(orq, cid, "CV-1", repo.fecha_referencia)
    assert envio.sesion is not None and envio.sesion.customer_id == cid
    assert repo.cliente(cid).nombre.split()[0] in envio.plantilla
    assert not re.search(r"\d", envio.plantilla)  # sin montos ni fechas
    assert envio.sesion.transcripcion == [("plantilla", envio.plantilla)]
    assert [p for p, _ in envio.pasos] == [
        "Disparador",
        "Filtro de contacto",
        "Segmento",
        "Plantilla",
        "Envío",
    ]
    contacto = repo.contactos(cid)[-1]
    assert contacto.campana_id == "CP-DEMO" and contacto.fecha.hour == 9


def test_un_solo_contacto_por_dia(orq, repo):
    assert que_sean_las_9(orq, DEMO[0], "CV-1", repo.fecha_referencia).sesion
    segundo = que_sean_las_9(orq, DEMO[0], "CV-2", repo.fecha_referencia)
    assert segundo.sesion is None and "hoy" in dict(segundo.pasos)["Filtro de contacto"]


@pytest.mark.parametrize(("cid", "motivo"), [("CL-1019515", "excluido"), ("CL-1125516", "grupo")])
def test_el_filtro_no_deja_enviar(orq, repo, cid, motivo):
    envio = que_sean_las_9(orq, cid, "CV-1", repo.fecha_referencia)
    assert envio.sesion is None and envio.plantilla is None
    assert motivo in dict(envio.pasos)["Filtro de contacto"]
    assert all(c.campana_id != "CP-DEMO" for c in repo.contactos(cid))


@pytest.mark.parametrize("segmento", list(_PLANTILLAS))
def test_plantillas_neutras_sin_gravedad_segmento_ni_montos(segmento):
    _, texto = plantilla(segmento, "Ana Pérez")
    assert texto.startswith(("Hola Ana,", "Ana,"))
    bajo = texto.lower()
    for palabra in (
        "varias",
        "preferente",
        "mora",
        "avanzada",
        "valioso",
        "reincid",
        "$",
        "usd",
        "b/.",
    ):
        assert palabra not in bajo
    assert not re.search(r"\d", texto)


def test_contacto_id_unico_por_cliente_y_dia(orq, repo):
    for cid in DEMO[:2]:
        que_sean_las_9(orq, cid, f"CV-{cid}", repo.fecha_referencia)
    ids = [
        c.contacto_id for cid in DEMO[:2] for c in repo.contactos(cid) if c.campana_id == "CP-DEMO"
    ]
    assert ids == [f"CT-{cid}-{repo.fecha_referencia:%Y%m%d}" for cid in DEMO[:2]]
