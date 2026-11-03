"""Servidor del agente en AgentCore Runtime (D46): contrato HTTP de su guía, puerto 8080.

    uvicorn agil.nube.runtime:app --host 0.0.0.0 --port 8080

`POST /invocations` recibe lo que arma `agente_remoto.pedido` y corre el turno del agente con el
repositorio en DynamoDB (tabla en la variable TABLA) y los modelos de Bedrock.
"""

import os
from functools import cache
from typing import Any

from fastapi import FastAPI

from agil.agente.config import Modelos, crear_modelos
from agil.agente.orquestador import Orquestador
from agil.dominio.repositorio.dynamo import RepositorioDynamo
from agil.nube.agente_remoto import atender_pedido
from agil.nube.recursos import tabla

app = FastAPI(title="Proyecto Ágil: agente")


@cache
def _modelos() -> Modelos:
    return crear_modelos()


@app.get("/ping")
def ping() -> dict:
    return {"status": "Healthy"}


@app.post("/invocations")
def invocations(datos: dict[str, Any]) -> dict[str, Any]:
    # Un repositorio por turno: lo leído no se reusa entre invocaciones.
    orq = Orquestador(RepositorioDynamo(tabla(os.environ["TABLA"])), _modelos())
    return atender_pedido(orq, datos)
