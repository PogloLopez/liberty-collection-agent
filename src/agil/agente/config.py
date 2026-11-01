"""Modelos del agente en Groq, vía su API compatible con OpenAI (D7, D26).

Solo el proveedor local: el de la nube (Bedrock) lo configura Pablo en el hito 4 y no cambia tools,
hooks ni prompts.
"""

import os
from dataclasses import dataclass

from strands.models import Model
from strands.models.openai import OpenAIModel

from agil.dominio.repositorio.memoria import RAIZ

GROQ_URL = "https://api.groq.com/openai/v1"
AGENTE = "openai/gpt-oss-120b"
ESTRATEGA = "openai/gpt-oss-20b"  # también escribe el resumen al cierre (D34)
MODERADOR = "openai/gpt-oss-safeguard-20b"  # D35


@dataclass
class Modelos:
    agente: Model
    estratega: Model | None = None
    moderador: Model | None = None


def _cargar_env() -> None:
    """Lee `.env` sin pisar variables ya definidas. La key nunca se imprime ni se versiona."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        clave, _, valor = linea.strip().partition("=")
        if clave and not clave.startswith("#"):
            os.environ.setdefault(clave.strip(), valor.strip().strip("\"'"))


def _groq(model_id: str, max_tokens: int) -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": os.environ["GROQ_API_KEY"], "base_url": GROQ_URL},
        model_id=model_id,
        params={"max_completion_tokens": max_tokens, "reasoning_effort": "low"},
    )


def crear_modelos() -> Modelos:
    _cargar_env()
    proveedor = os.environ.get("LLM_PROVIDER", "groq")
    if proveedor != "groq":
        raise NotImplementedError(f"Proveedor {proveedor!r}: en local solo existe 'groq'.")
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("Falta GROQ_API_KEY en .env")
    return Modelos(
        agente=_groq(AGENTE, 1500),
        estratega=_groq(ESTRATEGA, 600),
        moderador=_groq(MODERADOR, 300),
    )
