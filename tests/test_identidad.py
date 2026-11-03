import pytest

from agil.dominio.harness.identidad import enmascarar, extraer_digitos, ultimos_cuatro, verificar
from agil.dominio.repositorio.memoria import RepositorioMemoria


@pytest.mark.parametrize(
    ("cedula", "esperado"),
    [("6-712-982", "2982"), ("E-8-142908", "2908"), ("8-765-1043", "1043"), ("PE-3-1234", "1234")],
)
def test_ultimos_cuatro(cedula, esperado):
    assert ultimos_cuatro(cedula) == esperado


@pytest.mark.parametrize(
    ("mensaje", "esperado"),
    [
        ("1650", "1650"),
        ("a perdon 2908", "2908"),
        ("son 2 9 0 8", "2908"),
        ("mi cedula es E-8-142908", "2908"),
        ("8-765-1043", "1043"),
        ("PE-3-1234", "1234"),
        ("6-712-982 o E-8-142908", None),
        ("mire yo ahorita solo puedo dar 20", None),
        ("lo pago mañana 15", None),
        ("pago 140 dolares", None),
        ("1650 o 2908?", None),
        ("123456", None),
        ("hola", None),
        ("puedo pagar 25.50", None),
        ("lo pago el 15-02", None),
        ("lo pago el 15-02-2025", None),
        ("２９０８", None),
        ("13-765-1043", "1043"),
        ("E-13-142908", "2908"),
        ("14-765-1043", None),
        ("0-765-1043", None),
        ("E-14-142908", None),
        ("29 08", "2908"),
        ("2-9-0-8", None),
        ("2.9.0.8", None),
        ("2  9 0 8", None),
        ("lo pago el 12-11-2026", None),
        ("el 5-02-2026", None),
        ("mi ruc es 2398473-1-814562", None),
    ],
)
def test_extraer_digitos(mensaje, esperado):
    assert extraer_digitos(mensaje) == esperado


@pytest.mark.parametrize(
    ("mensaje", "esperado"),
    [
        ("13-85", "1385"),
        ("2.9.0.8", "2908"),
        (" 2 9-0.8 ", "2908"),
        ("13-855", None),
        ("hola", None),
    ],
)
def test_extraer_digitos_con_la_cedula_pedida_acepta_separadores(mensaje, esperado):
    assert extraer_digitos(mensaje, pedida=True) == esperado


def test_verificar():
    cliente = RepositorioMemoria().clientes()[0]
    correcto = ultimos_cuatro(cliente.cedula)
    assert verificar(cliente, correcto)
    assert not verificar(cliente, "0000" if correcto != "0000" else "1111")
    assert not verificar(cliente, cliente.cedula)
    assert not verificar(cliente, "")
    assert not verificar(cliente, "２９０８")  # dígitos Unicode: False, sin excepción


def test_enmascarar_sin_verificar_tapa_todo_digito():
    assert enmascarar("cédula 8-765-1043 y tel 6123 4567", solo_cedula=False) == (
        "cédula •-•••-•••• y tel •••• ••••"
    )


def test_enmascarar_verificado_solo_tapa_cedulas():
    assert enmascarar("le pago 50 el 15; mi cédula 8-765-1043", solo_cedula=True) == (
        "le pago 50 el 15; mi cédula •-•••-••••"
    )
