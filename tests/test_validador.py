import json
import unicodedata

import pytest

from agil.dominio.harness.placeholders import placeholders_en
from agil.dominio.harness.validador import validar_salida
from agil.dominio.repositorio.memoria import DATOS_MOCK

MAX = 400


def _textos_agente():
    conversaciones = json.loads(
        (DATOS_MOCK / "conversaciones_ejemplo.json").read_text(encoding="utf-8")
    )
    return [m["texto"] for c in conversaciones for m in c["mensajes"] if m["rol"] == "agente"]


def test_hay_ejemplos_de_agente():
    assert len(_textos_agente()) == 65


@pytest.mark.parametrize("texto", _textos_agente())
def test_textos_de_ejemplo_pasan(texto):
    v = validar_salida(texto, placeholders_en(texto), MAX)
    assert v.ok, v.motivo


@pytest.mark.parametrize(
    "texto",
    [
        "Tengo una opción para usted.",
        "Un momento, por favor.",
        "¿Me confirma los últimos cuatro dígitos de su cédula?",
        "El primer mes llega un cobro proporcional.",
        "Lo cambio para después de la quincena.",
        "Usted fue el primero en responder.",
        "Puede ir a la sucursal de Avenida Balboa.",
        "Mil gracias por su paciencia.",
        "Mil disculpas por la demora.",
        "Veo un pago registrado hoy.",
        "Mañana le confirmo por este medio.",
        "Si pagó ayer, gracias por avisar.",
        "Puede pagar dentro del plazo.",
        "Puede pagarla esta semana.",
        "Buen fin de semana.",
        unicodedata.normalize("NFD", "¿Me confirma los últimos cuatro dígitos?"),
    ],
)
def test_espanol_sin_falsos_positivos(texto):
    assert validar_salida(texto, set(), MAX).ok


@pytest.mark.parametrize(
    "texto",
    [
        "Su saldo es $47.85.",
        "Su saldo es 47.85.",
        "Puede pagar el 15 de noviembre.",
        "Puede pagar en noviembre.",
        "Le doy un 20% de descuento.",
        "Le doy un veinte por ciento.",
        "Son veinte dólares.",
        "Son B/. 30.",
        "Le escribo a las 3 pm.",
        "Le escribo a las tres de la tarde.",
        "Pague el viernes.",
        "En cuatro cuotas.",
        "Pague aquí: https://pagos.example.com/x",
        "Entre a www.liberty.com.pa",
        "Pague en liberty.com.pa",
        "Pague en pagos.liberty.app",
        "Son un millon.",
        "Son un millón.",
        "Pague el sabado.",
        "Le llamo a la una.",
        "Pague al mediodía.",
        "Pague el primero de mes.",
        "Pague el primero del mes.",
        "Pague hasta el día primero.",
        "Le llamo después de la una.",
        "Pague en PAGOS.LIBERTY.APP",
        "Son cientos.",
        "Le llamo a la  una.",
        "Pague el\nprimero del mes.",
        "Le doy un veinte por  ciento.",
        "Son diez balboas.",
        "Son cincuenta centavos.",
        "Pague pasado mañana.",
        "Le escribo la próxima semana.",
        "Lo vemos el mes que viene.",
        "Pague antes de fin de mes.",
        "Se refleja en unos días.",
        "Se aplica dentro de pocas horas.",
        "Pague la siguiente quincena.",
        "El próximo año.",
        "El año que viene.",
        "La semana siguiente.",
        "El mes entrante.",
        "Al final del mes.",
        "A finales de mes.",
        "En un par de días.",
        "Dentro de algunas semanas.",
        "En unos meses.",
        "En los próximos días se refleja.",
    ],
)
def test_bloquea_cifras_fechas_y_urls(texto):
    v = validar_salida(texto, set(), MAX)
    assert not v.ok and v.motivo


def test_cifra_dentro_de_placeholder_permitido():
    permitidos = {"monto_cuota", "fecha_promesa"}
    assert validar_salida("Pague {{monto_cuota}} el {{fecha_promesa}}.", permitidos, MAX).ok


def test_placeholder_desconocido():
    v = validar_salida("Su descuento es {{descuento_extra}}.", {"saldo_vencido"}, MAX)
    assert not v.ok and "descuento_extra" in v.motivo


def test_placeholder_mal_formado():
    assert not validar_salida("Saldo {{ saldo_vencido }}", {"saldo_vencido"}, MAX).ok
    assert not validar_salida("Saldo {saldo_vencido}", {"saldo_vencido"}, MAX).ok


def test_texto_demasiado_largo():
    v = validar_salida("Hola. " * 100, set(), MAX)
    assert not v.ok and "largo" in v.motivo
    assert validar_salida("Hola.", set(), 5).ok


def test_tildes_en_forma_nfd_se_bloquean():
    for texto in ("Son un millón.", "Pague el miércoles."):
        assert not validar_salida(unicodedata.normalize("NFD", texto), set(), MAX).ok


def test_punto_sin_espacio_no_es_url():
    assert validar_salida("Gracias.Hoy le escribo.", set(), MAX).ok
