"""La app local con un modelo guionado: sin red ni key (D38)."""

import pytest
from conftest import ModeloGuionado
from fastapi.testclient import TestClient

from agil.agente.config import Modelos
from agil.app.api import crear_app
from agil.dominio.harness.identidad import ultimos_cuatro

CID = "CL-1171492"


@pytest.fixture
def cliente(repo):
    def crear(*guion, modo_demo=False):
        return TestClient(crear_app(repo, Modelos(agente=ModeloGuionado(*guion)), modo_demo))

    return crear


def _abrir(http) -> str:
    r = http.post("/api/campana", json={"customer_id": CID}).json()
    assert r["conversacion_id"] and r["plantilla"].startswith("Hola Itzel")
    return r["conversacion_id"]


def test_lista_los_candidatos_de_demo_con_su_segmento(cliente):
    lista = cliente().get("/api/clientes").json()
    assert {
        "customer_id": CID,
        "nombre": "Itzel Marisol Quintero Batista",
        "segmento": "olvidadizo",
    } in lista
    assert len({c["segmento"] for c in lista}) == 5


def test_conversacion_completa_con_tarjeta_y_boton(cliente, repo):
    http = cliente(
        "Para ayudarle, ¿me indica los últimos cuatro dígitos de su cédula?",
        ("registrar_promesa_pago", {"fecha": "mañana"}),
    )
    cv = _abrir(http)
    http.post(f"/api/conversaciones/{cv}/mensajes", json={"texto": "hola, se me pasó"})
    digitos = ultimos_cuatro(repo.cliente(CID).cedula)
    r = http.post(f"/api/conversaciones/{cv}/mensajes", json={"texto": digitos}).json()
    assert r["tarjeta"]["tipo"] == "promesa" and r["mensajes"] == []
    assert ["Verificación de cédula", "correcta"] in r["pasos"]

    r = http.post(f"/api/conversaciones/{cv}/botones", json={"boton": "btn_confirmar"}).json()
    assert r["mensajes"][0].startswith("Listo, Itzel. Quedó registrada") and not r["cerrada"]
    cartera = http.get("/api/cartera").json()
    assert len(cartera["promesas"]) == 1 and cartera["links"]
    conversacion = cartera["conversaciones"][0]
    assert conversacion["conversacion_id"] == cv and not conversacion["cerrada"]
    assert digitos not in str(conversacion["transcripcion"])


def test_conversacion_desconocida_da_404(cliente):
    http = cliente()
    assert http.post("/api/conversaciones/CV-X/mensajes", json={"texto": "hola"}).status_code == 404
    assert (
        http.post("/api/conversaciones/CV-X/botones", json={"boton": "btn_confirmar"}).status_code
        == 404
    )


def test_campana_de_cliente_desconocido_da_404(cliente):
    assert cliente().post("/api/campana", json={"customer_id": "CL-0"}).status_code == 404


def test_boton_invalido_da_422(cliente):
    http = cliente()
    cv = _abrir(http)
    assert (
        http.post(f"/api/conversaciones/{cv}/botones", json={"boton": "pagar"}).status_code == 422
    )


def test_campana_bloqueada_no_abre_conversacion(cliente):
    http = cliente()
    _abrir(http)
    r = http.post("/api/campana", json={"customer_id": CID}).json()  # segundo contacto del día
    assert r["conversacion_id"] is None and r["plantilla"] is None
    assert len(http.get("/api/cartera").json()["conversaciones"]) == 1


def test_modo_demo_abre_otra_conversacion_con_el_mismo_cliente(cliente):
    http = cliente(modo_demo=True)
    assert _abrir(http) != _abrir(http)


def test_sirve_el_frontend(cliente):
    http = cliente()
    assert "Proyecto Ágil" in http.get("/").text
    assert http.get("/app.js").status_code == 200


def test_escalamiento_cierra_y_la_cartera_muestra_el_handoff(repo):
    escalar = ("escalar_a_humano", {"motivo": "pide_humano", "resumen": "Pide asesor."})
    agente = ModeloGuionado(escalar, "Un asesor le escribirá.")
    http = TestClient(crear_app(repo, Modelos(agente=agente)))
    cv = _abrir(http)
    r = http.post(f"/api/conversaciones/{cv}/mensajes", json={"texto": "quiero un humano"}).json()
    assert r["cerrada"]
    cartera = http.get("/api/cartera").json()
    assert [h["motivo"] for h in cartera["handoffs"]] == ["pide_humano"]
    conversacion = cartera["conversaciones"][0]
    assert conversacion["cerrada"] and conversacion["motivo_cierre"] == "handoff"

    llamadas = len(agente.recibido)
    r = http.post(f"/api/conversaciones/{cv}/mensajes", json={"texto": "¿sigue ahí?"}).json()
    assert r["cerrada"] and r["mensajes"] == [] and r["tarjeta"] is None
    assert len(agente.recibido) == llamadas  # cerrada: no se llama al agente


def test_mensaje_sin_texto_da_422(cliente):
    http = cliente()
    cv = _abrir(http)
    assert http.post(f"/api/conversaciones/{cv}/mensajes", json={}).status_code == 422


def test_sin_modelos_lee_modo_demo_de_la_config(repo, monkeypatch):
    from types import SimpleNamespace

    import agil.app.api as api

    monkeypatch.setattr(api, "Configuracion", lambda: SimpleNamespace(modo_demo=True))
    monkeypatch.setattr(api, "crear_modelos", lambda cfg: Modelos(agente=ModeloGuionado()))
    http = TestClient(crear_app(repo))
    assert _abrir(http) != _abrir(http)
