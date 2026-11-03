"""Piezas de la nube sin red (D46): DynamoDB simulado con moto y el turno remoto en el proceso."""

import io
import json
import re
from datetime import date, datetime

import boto3
import pytest
from conftest import ModeloGuionado
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from moto import mock_aws

from agil.agente.config import Modelos
from agil.agente.orquestador import Orquestador
from agil.app.api import ESTATICOS, Backend, montar
from agil.app.campana import que_sean_las_9
from agil.app.sesiones import SesionesDynamo
from agil.dominio.harness.identidad import ultimos_cuatro
from agil.dominio.modelos import Cola, Handoff, Nota
from agil.dominio.repositorio.dynamo import RepositorioDynamo, reiniciar, sembrar
from agil.dominio.repositorio.memoria import RepositorioMemoria
from agil.nube import lambda_api, recursos
from agil.nube.agente_remoto import OrquestadorRemoto, atender_pedido, invocador_runtime, pedido

CID = "CL-1171492"
AHORA = datetime.fromisoformat("2026-11-06T10:00:00-05:00")


@pytest.fixture
def tabla_vacia(monkeypatch):
    for k, v in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        t = boto3.resource("dynamodb").create_table(
            TableName="agil",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield t


@pytest.fixture
def tabla(tabla_vacia):
    reiniciar(tabla_vacia)
    return tabla_vacia


def test_dynamo_lee_lo_mismo_que_memoria(tabla):
    mem, dyn = RepositorioMemoria(), RepositorioDynamo(tabla)
    assert dyn.fecha_referencia == mem.fecha_referencia and dyn.parametros == mem.parametros
    assert dyn.clientes() == mem.clientes() and dyn.ofertas() == mem.ofertas()
    for c in mem.clientes():
        cid = c.customer_id
        assert dyn.facturas(cid) == mem.facturas(cid)
        assert dyn.pagos(cid) == mem.pagos(cid)
        assert dyn.score(cid) == mem.score(cid)
        assert dyn.contactos(cid) == mem.contactos(cid)
        assert dyn.notas(cid) == mem.notas(cid)
    tel = mem.clientes()[0].telefono_whatsapp
    assert dyn.cliente_por_telefono(tel) == mem.cliente_por_telefono(tel)
    assert dyn.cliente("CL-0") is None and dyn.facturas("CL-0") == [] and dyn.score("CL-0") is None


def test_dynamo_escrituras_persisten_entre_instancias(tabla):
    repo = RepositorioDynamo(tabla)
    antes = len(repo.notas(CID))
    nota = Nota(nota_id="N-T", customer_id=CID, fecha=AHORA, origen="agente", texto="x", flags=[])
    repo.guardar_nota(nota)
    handoff = Handoff(
        handoff_id="H", customer_id=CID, cola=Cola.basica, motivo="m", resumen="r", creado=AHORA
    )
    repo.guardar_handoff(handoff)
    repo.pausar_whatsapp(CID, date(2026, 11, 6))
    otra = RepositorioDynamo(tabla)  # la siguiente invocación
    assert len(otra.notas(CID)) == antes + 1 and otra.notas(CID)[-1] == nota
    assert otra.escrituras("handoffs") == [handoff]
    assert otra.cliente(CID).whatsapp_pausado
    reiniciar(tabla)
    assert RepositorioDynamo(tabla).escrituras("handoffs") == []


def test_sesiones_en_dynamo_ida_y_vuelta(tabla):
    repo = RepositorioDynamo(tabla)
    orq = Orquestador(repo, Modelos(ModeloGuionado()), lambda: AHORA)
    envio = que_sean_las_9(orq, CID, "CV-001", repo.fecha_referencia, modo_demo=True)
    sesiones = SesionesDynamo(tabla)
    sesiones.guardar(envio.sesion)
    assert sesiones.cargar("CV-001") == envio.sesion
    assert [s.conversacion_id for s in sesiones.todas()] == ["CV-001"]
    assert sesiones.cargar("CV-X") is None
    reiniciar(tabla)
    assert sesiones.todas() == []


def test_turno_remoto_da_lo_mismo_que_el_local():
    """El Runtime se simula en el proceso: el pedido viaja serializado a JSON y vuelve."""
    guion = ("¿Me da los cuatro dígitos de su cédula?", "Su saldo está listo.")

    def correr(remoto: bool):
        repo = RepositorioMemoria()
        agente = ModeloGuionado(*guion)
        local = Orquestador(repo, Modelos(agente), lambda: AHORA)
        orq = local
        if remoto:
            orq = OrquestadorRemoto(
                repo,
                Modelos(ModeloGuionado()),
                lambda: AHORA,
                invocar=lambda d: json.loads(
                    json.dumps(atender_pedido(local, json.loads(json.dumps(d))))
                ),
            )
        sesion = orq.iniciar(CID, "CV-1", "plantilla")
        respuestas = [
            orq.atender(sesion, "hola"),
            orq.atender(sesion, ultimos_cuatro(repo.cliente(CID).cedula)),
        ]
        return sesion, respuestas

    def sin_tracking(s):  # Strands pone un tracking_id al azar en cada mensaje
        d = s.model_dump()
        for m in d["historial"]:
            m.pop("tracking_id", None)
        return d

    s_local, r_local = correr(remoto=False)
    s_remoto, r_remoto = correr(remoto=True)
    assert r_remoto == r_local
    assert sin_tracking(s_remoto) == sin_tracking(s_local)
    assert s_remoto.verificada and dict(r_remoto[1].pasos)["Verificación de cédula"] == "correcta"


def test_pedido_lleva_recien_verificada():
    repo = RepositorioMemoria()
    sesion = Orquestador(repo, Modelos(ModeloGuionado()), lambda: AHORA).iniciar(CID, "CV-1")
    sesion.recien_verificada = True
    assert pedido(sesion, "Cliente: hola")["recien_verificada"] is True


def test_api_con_dynamo(tabla):
    """La misma API, con repositorio y sesiones en DynamoDB y un repositorio nuevo por request."""
    modelos = Modelos(ModeloGuionado("¿Me da los cuatro dígitos de su cédula?"))

    def campana(repo, customer_id, conversacion_id):
        orq = Orquestador(repo, modelos, lambda: AHORA)
        envio = que_sean_las_9(orq, customer_id, conversacion_id, repo.fecha_referencia, True)
        if envio.sesion:
            sesiones.guardar(envio.sesion)
        return envio.model_dump(mode="json")

    sesiones = SesionesDynamo(tabla)
    http = TestClient(
        montar(
            Backend(
                repo=lambda: RepositorioDynamo(tabla),
                orquestador=lambda r: Orquestador(r, modelos, lambda: AHORA),
                sesiones=sesiones,
                campana=campana,
                reiniciar=lambda: reiniciar(tabla),
            ),
            modo_demo=True,
        )
    )
    cv = http.post("/api/campana", json={"customer_id": CID}).json()["conversacion_id"]
    r = http.post(f"/api/conversaciones/{cv}/mensajes", json={"texto": "hola"}).json()
    assert r["pide_cedula"]
    cartera = http.get("/api/cartera").json()
    assert cartera["conversaciones"][0]["turno"] == 1
    assert http.post("/api/reiniciar").json() == {"ok": True}
    assert http.get("/api/cartera").json()["conversaciones"] == []


def test_tabla_vacia_se_siembra_sola_y_sembrar_no_duplica(tabla_vacia):
    repo = RepositorioDynamo(tabla_vacia)  # autosiembra en __init__
    assert repo.fecha_referencia == RepositorioMemoria().fecha_referencia
    assert repo.cliente(CID) is not None
    n = tabla_vacia.scan(Select="COUNT")["Count"]
    assert sembrar(tabla_vacia) == n
    assert tabla_vacia.scan(Select="COUNT")["Count"] == n


def _backend_minimo(tabla, **kw) -> Backend:
    def campana(repo, customer_id, conversacion_id):
        orq = Orquestador(repo, Modelos(ModeloGuionado()), lambda: AHORA)
        return que_sean_las_9(
            orq, customer_id, conversacion_id, repo.fecha_referencia, True
        ).model_dump(mode="json")

    return Backend(
        repo=lambda: RepositorioDynamo(tabla),
        orquestador=lambda r: Orquestador(r, Modelos(ModeloGuionado()), lambda: AHORA),
        sesiones=SesionesDynamo(tabla),
        campana=campana,
        reiniciar=lambda: reiniciar(tabla),
        **kw,
    )


def test_codigo_de_acceso_solo_en_api(tabla):
    app = montar(_backend_minimo(tabla), modo_demo=True, codigo="secreto")
    app.mount("/", StaticFiles(directory=ESTATICOS, html=True), name="estaticos")
    http = TestClient(app)
    assert http.get("/api/demo").status_code == 401
    assert http.get("/api/demo", headers={"x-codigo-acceso": "otro"}).status_code == 401
    assert http.get("/api/demo", headers={"x-codigo-acceso": "secreto"}).status_code == 200
    assert http.get("/").status_code == 200  # el frontend estático no lo exige


def test_nuevo_id_del_backend_se_usa(tabla):
    http = TestClient(montar(_backend_minimo(tabla, nuevo_id=lambda: "CV-NUBE"), modo_demo=True))
    assert (
        http.post("/api/campana", json={"customer_id": CID}).json()["conversacion_id"] == "CV-NUBE"
    )
    assert re.fullmatch(r"CV-\d{6}-[0-9a-f]{4}", lambda_api._nuevo_id())


@pytest.fixture
def lambda_env(tabla, monkeypatch):
    monkeypatch.setenv("TABLA", "agil")
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("MODO_DEMO", "true")
    monkeypatch.setattr(lambda_api, "_modelos", lambda: Modelos(ModeloGuionado()))
    recursos.tabla.cache_clear()
    lambda_api._cfg.cache_clear()
    yield tabla
    recursos.tabla.cache_clear()
    lambda_api._cfg.cache_clear()


def test_lambdas_de_la_campana(lambda_env):
    evento = {"customer_id": CID, "conversacion_id": "CV-L1"}
    paso1 = lambda_api.filtro(evento, None)
    assert paso1["ok"] is True and paso1["sesion"] is None and paso1["customer_id"] == CID
    paso2 = lambda_api.envio(json.loads(json.dumps(paso1)), None)
    assert paso2["plantilla"] and paso2["sesion"]["conversacion_id"] == "CV-L1"
    guardada = SesionesDynamo(lambda_env).cargar("CV-L1")
    assert guardada is not None and guardada.customer_id == CID


def test_invocador_runtime_con_cliente_falso():
    llamadas = []

    class ClienteFalso:
        def invoke_agent_runtime(self, **kw):
            llamadas.append(kw)
            return {"statusCode": 200, "response": io.BytesIO(b'{"respuesta": {"texto": "ok"}}')}

    invocar = invocador_runtime(ClienteFalso(), "arn:falso")
    datos = {"sesion": {"conversacion_id": "CV-1"}, "linea_cliente": "hola"}
    assert invocar(datos) == {"respuesta": {"texto": "ok"}}
    kw = llamadas[0]
    assert kw["agentRuntimeArn"] == "arn:falso"
    assert len(kw["runtimeSessionId"]) >= 33 and "CV-1" in kw["runtimeSessionId"]
    assert kw["contentType"] == kw["accept"] == "application/json"
    assert json.loads(kw["payload"]) == datos


def test_runtime_http(lambda_env, monkeypatch):
    from agil.nube import runtime

    monkeypatch.setattr(runtime, "_modelos", lambda: Modelos(ModeloGuionado("Hola.")))
    http = TestClient(runtime.app)
    assert http.get("/ping").json() == {"status": "Healthy"}
    repo = RepositorioDynamo(lambda_env)
    sesion = Orquestador(repo, Modelos(ModeloGuionado()), lambda: AHORA).iniciar(CID, "CV-R")
    r = http.post("/invocations", json=pedido(sesion, "Cliente: hola")).json()
    assert r["sesion"]["conversacion_id"] == "CV-R" and "respuesta" in r and "pasos" in r
