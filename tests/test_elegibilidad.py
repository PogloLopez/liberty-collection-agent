"""Elegibilidad para contacto contra el oráculo y el filtro antes de cada envío."""

import json
from datetime import date, datetime

import pytest

from agil.dominio.modelos import MotivoNoElegible
from agil.dominio.reglas.calendario import ZONA
from agil.dominio.reglas.elegibilidad import elegible_para_contacto, puede_enviar_ahora
from agil.dominio.repositorio.memoria import DATOS_MOCK, RepositorioMemoria

ORACULO = json.loads((DATOS_MOCK / "etiquetas_esperadas.json").read_text(encoding="utf-8"))
REPO = RepositorioMemoria()


def _pa(*args: int) -> datetime:
    return datetime(*args, tzinfo=ZONA)


@pytest.mark.parametrize("esperado", ORACULO, ids=lambda e: e["customer_id"])
def test_elegibilidad_coincide_con_oraculo(esperado):
    e = elegible_para_contacto(REPO, esperado["customer_id"])
    assert e.elegible is esperado["elegible_contacto"]
    assert e.motivos == esperado["motivos_no_elegible"]


def test_pago_en_transito_que_cubre_el_saldo_bloquea():
    e = elegible_para_contacto(REPO, "CL-1190560")
    assert e.motivos == [MotivoNoElegible.pago_en_transito_cubre_saldo]


def test_pago_en_transito_parcial_no_bloquea():
    assert elegible_para_contacto(REPO, "CL-1173697").elegible


def test_pausar_whatsapp_vuelve_no_elegible():
    repo = RepositorioMemoria()
    repo.pausar_whatsapp("CL-1171492", date(2026, 11, 6))
    motivos = elegible_para_contacto(repo, "CL-1171492").motivos
    assert motivos == [MotivoNoElegible.whatsapp_pausado]


def test_puede_enviar_en_horario_y_sin_contacto_del_dia():
    assert puede_enviar_ahora(REPO, "CL-1171492", _pa(2026, 11, 6, 9, 0)).ok


def test_no_envia_dos_veces_el_mismo_dia():
    v = puede_enviar_ahora(REPO, "CL-1171492", _pa(2026, 11, 4, 15, 0))
    assert not v.ok
    assert v.motivo


def test_no_envia_fuera_de_horario():
    assert not puede_enviar_ahora(REPO, "CL-1171492", _pa(2026, 11, 6, 18, 0)).ok
    assert not puede_enviar_ahora(REPO, "CL-1171492", _pa(2026, 11, 3, 10, 0)).ok


def test_no_envia_si_no_es_elegible():
    v = puede_enviar_ahora(REPO, "CL-1125516", _pa(2026, 11, 6, 9, 0))
    assert not v.ok
    assert "grupo_control" in v.motivo


def test_sin_saldo_vencido_no_se_envia():
    repo = RepositorioMemoria()
    repo._facturas = [
        f.model_copy(update={"estado": "pagada"}) if f.customer_id == "CL-1171492" else f
        for f in repo._facturas
    ]
    resultado = puede_enviar_ahora(repo, "CL-1171492", _pa(2026, 11, 6, 10))
    assert not resultado.ok
    assert "saldo" in resultado.motivo


def test_cliente_inexistente_lanza_key_error():
    with pytest.raises(KeyError):
        elegible_para_contacto(REPO, "CL-0000000")
    with pytest.raises(KeyError):
        puede_enviar_ahora(REPO, "CL-0000000", _pa(2026, 11, 6, 9, 0))
