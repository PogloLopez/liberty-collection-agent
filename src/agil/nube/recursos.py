"""Clientes de la SDK de AWS, creados una vez por proceso. Solo se usan en la nube (D46)."""

from functools import cache
from typing import Any

import boto3
from botocore.config import Config


@cache
def tabla(nombre: str) -> Any:
    return boto3.resource("dynamodb").Table(nombre)


@cache
def cliente(servicio: str) -> Any:
    return boto3.client(servicio)


@cache
def cliente_runtime() -> Any:
    """Sin reintentos: un turno repetido correría dos veces en el Runtime (doble costo y escrituras
    sin los IDs del primero). Corta antes que CloudFront (60 s) para responder un error limpio."""
    return boto3.client(
        "bedrock-agentcore",
        config=Config(read_timeout=55, connect_timeout=5, retries={"max_attempts": 1}),
    )
