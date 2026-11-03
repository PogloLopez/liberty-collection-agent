"""Segmentación contra el oráculo (segmento y cola, D17) y umbrales leídos de meta.json."""

import json

import pytest

from agil.dominio.modelos import Cola, Segmento
from agil.dominio.reglas.segmentacion import segmentar
from agil.dominio.repositorio.memoria import DATOS_MOCK, RepositorioMemoria

ORACULO = json.loads((DATOS_MOCK / "etiquetas_esperadas.json").read_text(encoding="utf-8"))
REPO = RepositorioMemoria()


@pytest.mark.parametrize("esperado", ORACULO, ids=lambda e: e["customer_id"])
def test_segmento_y_cola_coinciden_con_oraculo(esperado):
    s = segmentar(REPO, esperado["customer_id"])
    assert s.segmento == esperado["segmento_esperado"]
    assert s.cola_escalamiento == esperado["cola_escalamiento"]
    assert s.variables.model_dump(mode="json") == esperado["variables"]
    assert s.motivo


@pytest.mark.parametrize(
    ("customer_id", "segmento"),
    [
        ("CL-1197204", Segmento.olvidadizo),
        ("CL-1203027", Segmento.dificultad_temporal),
        ("CL-1168863", Segmento.dificultad_temporal),
        ("CL-1183069", Segmento.mora_avanzada),
        ("CL-1165562", Segmento.reincidente),
        ("CL-1181514", Segmento.dificultad_temporal),
        ("CL-1262023", Segmento.mora_avanzada),
        ("CL-1215806", Segmento.dificultad_temporal),
        ("CL-1107377", Segmento.dificultad_temporal),
        ("CL-1195028", Segmento.dificultad_temporal),
        ("CL-1178922", Segmento.olvidadizo),
        ("CL-1080054", Segmento.valioso_churn),
        ("CL-1252202", Segmento.valioso_churn),
        ("CL-1121736", Segmento.reincidente),
        ("CL-1190560", Segmento.olvidadizo),
    ],
)
def test_casos_borde(customer_id, segmento):
    assert segmentar(REPO, customer_id).segmento is segmento


@pytest.mark.parametrize(
    ("customer_id", "cola"),
    [
        ("CL-1161090", Cola.reclamos),
        ("CL-1019515", Cola.especializada),
        ("CL-1123976", None),
        ("CL-1248251", None),
    ],
)
def test_cola_de_excluidos(customer_id, cola):
    s = segmentar(REPO, customer_id)
    assert s.segmento is Segmento.excluido
    assert s.cola_escalamiento == cola


def test_score_vencido_se_explica_en_el_motivo():
    assert "conservador" in segmentar(REPO, "CL-1215806").motivo


@pytest.mark.parametrize(
    ("parametro", "valor", "customer_id", "segmento"),
    [
        ("dias_mora_olvidadizo_max", 16, "CL-1203027", Segmento.olvidadizo),
        ("dias_mora_avanzada_min", 60, "CL-1168863", Segmento.mora_avanzada),
        ("moras_reincidente_min", 2, "CL-1181514", Segmento.reincidente),
        ("saldo_monto_alto_usd", "450.00", "CL-1262023", Segmento.dificultad_temporal),
        ("antiguedad_valioso_min_meses", 25, "CL-1252202", Segmento.dificultad_temporal),
    ],
)
def test_umbrales_salen_de_meta(parametro, valor, customer_id, segmento):
    repo = RepositorioMemoria()
    repo.parametros = {**repo.parametros, parametro: valor}
    assert segmentar(repo, customer_id).segmento is segmento


def test_cliente_inexistente_lanza_keyerror():
    with pytest.raises(KeyError):
        segmentar(REPO, "CL-0000000")
