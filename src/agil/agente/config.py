"""Modelos del agente según `config.yaml` y `.env` (D7, D26, D36).

Solo el proveedor local (Groq, vía su API compatible con OpenAI): el de la nube (Bedrock) lo
configura Pablo en el hito 4 y no cambia tools, hooks ni prompts. Las variables de entorno pisan al
`.env`.
"""

import logging
from dataclasses import dataclass
from typing import Literal, Self

from opentelemetry import trace
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from strands.models import Model
from strands.models.openai import OpenAIModel
from strands.types.exceptions import ContextWindowOverflowException

from agil.dominio.repositorio.memoria import RAIZ

log = logging.getLogger(__name__)


class Rol(BaseModel):
    modelos: list[str] = Field(min_length=1)  # en orden; los siguientes son alternativas
    max_tokens: int


class Entorno(BaseModel):
    proveedor: Literal["groq", "bedrock"]
    url: str | None = None
    timeout_s: float
    agente: Rol
    estratega: Rol | None = None
    moderador: Rol | None = None


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env", yaml_file=RAIZ / "config.yaml", extra="ignore"
    )

    llm_provider: Literal["groq", "bedrock"] = "groq"
    groq_api_key: SecretStr | None = None
    dev: Entorno
    prod: Entorno

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, **_
    ):
        return init_settings, env_settings, dotenv_settings, YamlConfigSettingsSource(settings_cls)

    @property
    def entorno(self) -> Entorno:
        return self.dev if self.dev.proveedor == self.llm_provider else self.prod

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        secciones = [e for e in (self.dev, self.prod) if e.proveedor == self.llm_provider]
        if len(secciones) != 1:
            raise ValueError(f"config.yaml necesita una sola sección de {self.llm_provider}")
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("Falta GROQ_API_KEY en .env")
        return self


@dataclass
class Modelos:
    agente: Model
    estratega: Model | None = None
    moderador: Model | None = None


def _vacia(eventos: list[dict]) -> bool:
    """Sin texto ni tool: cuenta como fallo del modelo."""
    for e in eventos:
        if "toolUse" in e.get("contentBlockStart", {}).get("start", {}):
            return False
        if e.get("contentBlockDelta", {}).get("delta", {}).get("text", "").strip():
            return False
    return True


class ConRespaldo(Model):
    """Prueba los modelos en orden con la regla de fallo de D36. La respuesta se acumula antes de
    emitirla (WhatsApp no necesita streaming): una alternativa nunca recibe un `toolUse` a medias.
    La ventana de contexto excedida no cae al siguiente: el bucle de Strands recorta y reintenta.
    """

    def __init__(self, modelos: list[Model]) -> None:
        self.modelos = modelos

    def update_config(self, **model_config) -> None:
        for m in self.modelos:
            m.update_config(**model_config)

    def get_config(self):
        return self.modelos[0].get_config()

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        async for evento in self.modelos[0].structured_output(
            output_model, prompt, system_prompt, **kwargs
        ):
            yield evento

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        error: Exception = RuntimeError("Respuesta vacía de todos los modelos")
        cancelado = kwargs.get("cancel_signal")
        for m in self.modelos:
            if cancelado is not None and cancelado.is_set():
                break
            model_id = m.get_config().get("model_id")
            try:
                eventos = [e async for e in m.stream(messages, tool_specs, system_prompt, **kwargs)]
            except ContextWindowOverflowException:
                raise
            except Exception as e:
                error, motivo = e, type(e).__name__
            else:
                if not _vacia(eventos):
                    for e in eventos:
                        yield e
                    return
                motivo = "vacia"
            log.warning("Falló %s (%s); se prueba el siguiente", model_id, motivo)
            trace.get_current_span().add_event("respaldo", {"modelo": model_id, "motivo": motivo})
        raise error


def _groq(cfg: Configuracion, entorno: Entorno, model_id: str, max_tokens: int) -> OpenAIModel:
    return OpenAIModel(
        client_args={
            "api_key": cfg.groq_api_key.get_secret_value(),
            "base_url": entorno.url,
            "timeout": entorno.timeout_s,
        },
        model_id=model_id,
        params={"max_completion_tokens": max_tokens, "reasoning_effort": "low"},
    )


def crear_modelos(cfg: Configuracion | None = None) -> Modelos:
    cfg = cfg or Configuracion()
    entorno = cfg.entorno
    if entorno.proveedor != "groq":
        raise NotImplementedError(f"Proveedor {entorno.proveedor!r}: en local solo existe 'groq'.")

    def rol(r: Rol | None) -> Model | None:
        if r is None:
            return None
        modelos = [_groq(cfg, entorno, m, r.max_tokens) for m in r.modelos]
        return modelos[0] if len(modelos) == 1 else ConRespaldo(modelos)

    return Modelos(
        agente=rol(entorno.agente),
        estratega=rol(entorno.estratega),
        moderador=rol(entorno.moderador),
    )
