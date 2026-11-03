import pytest

from agil.dominio.harness.placeholders import placeholders_en, renderizar


def test_placeholders_en():
    texto = "Su saldo es {{saldo_vencido}}; descuento {{oferta.descuento}}. Link: {{link_pago}}"
    assert placeholders_en(texto) == {"saldo_vencido", "oferta.descuento", "link_pago"}


def test_ignora_formas_invalidas():
    assert placeholders_en("{saldo} {{ saldo }} {{Saldo}} {{1x}} sin nada") == set()


def test_renderizar():
    texto = "Saldo {{saldo_vencido}}, otra vez {{saldo_vencido}}, {{oferta.descuento}}"
    valores = {"saldo_vencido": "$47.85", "oferta.descuento": "10%"}
    assert renderizar(texto, valores) == "Saldo $47.85, otra vez $47.85, 10%"


def test_renderizar_falla_si_falta_valor():
    with pytest.raises(ValueError):
        renderizar("Saldo {{saldo_vencido}}", {})


def test_renderizar_falla_si_mal_formado():
    with pytest.raises(ValueError):
        renderizar("Saldo {{ saldo_vencido }}", {"saldo_vencido": "1"})


def test_valor_con_llaves_no_se_reinterpreta():
    assert renderizar("{{a}}", {"a": "{{b}}"}) == "{{b}}"


@pytest.mark.parametrize("texto", ["Saldo {saldo_vencido}", "Saldo {{saldo", "{{{a}}}"])
def test_renderizar_rechaza_llaves_sueltas(texto):
    with pytest.raises(ValueError):
        renderizar(texto, {"a": "1", "saldo_vencido": "1"})


def test_valor_con_referencias_de_regex_se_copia_literal():
    assert renderizar("{{a}}", {"a": r"\1 \g<0>"}) == r"\1 \g<0>"
