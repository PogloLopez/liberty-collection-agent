"""Modelos del agente según `config.yaml` y `.env` (D7, D26, D36).

En local, Groq vía su API compatible con OpenAI; en la nube, Bedrock con Guardrails (D46). Cambiar
de proveedor no cambia tools, hooks ni prompts. Las variables de entorno pisan al `.env`.
"""

import logging
from dataclasses import dataclass
from typing import Literal, Self

from botocore.config import Config
from opentelemetry import trace
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from strands.models import Model
from strands.models.bedrock import BedrockModel
from strands.models.openai import OpenAIModel
from strands.types.exceptions import ContextWindowOverflowException, ModelThrottledException

from agil.dominio.repositorio.memoria import RAIZ

log = logging.getLogger(__name__)


class Rol(BaseModel):
    modelos: list[str] = Field(min_length=1)  # en orden; los siguientes son alternativas
    max_tokens: int


class Entorno(BaseModel):
    proveedor: Literal["groq", "bedrock"]
    url: str | None = None
    region: str | None = None
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
    # En la nube la key no viaja en variables: el stack pasa el nombre del parámetro cifrado (D50).
    groq_api_key_param: str | None = None
    modo_demo: bool = False  # sin el tope de un contacto por día (D38)
    guardrail_id: str | None = None  # los pone el stack en la nube (D4, D24, D46)
    guardrail_version: str | None = None
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
        if self.llm_provider == "groq" and not self.groq_api_key and self.groq_api_key_param:
            key = leer_parametro(self.groq_api_key_param, self.prod.region)
            self.groq_api_key = SecretStr(key)
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("Falta GROQ_API_KEY en .env")
        return self


def leer_parametro(nombre: str, region: str | None) -> str:
    """Un SecureString de SSM Parameter Store, descifrado (D50). Solo en la nube, en la región de
    la demo (D47)."""
    import boto3  # aquí y no arriba: en local no hace falta la SDK

    with trace.get_tracer("agil.config").start_as_current_span("agil.leer_parametro") as span:
        span.set_attribute("agil.parametro", nombre)
        respuesta = boto3.client("ssm", region_name=region).get_parameter(
            Name=nombre, WithDecryption=True
        )
        return respuesta["Parameter"]["Value"]


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
        for i, m in enumerate(self.modelos):
            if cancelado is not None and cancelado.is_set():
                break
            model_id = m.get_config().get("model_id")
            try:
                eventos = [e async for e in m.stream(messages, tool_specs, system_prompt, **kwargs)]
            except ModelThrottledException as e:
                diaria = "per day" in str(e)
                if not diaria and i == len(self.modelos) - 1:  # el último: Strands espera (D41)
                    trace.get_current_span().add_event("cuota", {"modelo": model_id})
                    raise
                # Diaria: esperar no sirve (D42). Por minuto: el siguiente tiene su propia cuota y
                # esperar no cabe en los 55 s que la Lambda espera al Runtime (D50).
                error, motivo = e, "cuota_diaria" if diaria else "cuota_minuto"
            except ContextWindowOverflowException:
                raise  # Strands recorta y reintenta
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


# Razonamiento corto en gpt-oss; en qwen, fuera del texto: por defecto va en `content` (D42).
# `reasoning_format` es propio de Groq: el SDK de OpenAI solo lo acepta en `extra_body` (D50).
_RAZONAMIENTO = {
    "openai/gpt-oss": {"reasoning_effort": "low"},
    "qwen/": {"extra_body": {"reasoning_format": "hidden"}},
}


def _groq(cfg: Configuracion, entorno: Entorno, model_id: str, max_tokens: int) -> OpenAIModel:
    extra = next((p for pre, p in _RAZONAMIENTO.items() if model_id.startswith(pre)), {})
    return OpenAIModel(
        client_args={
            "api_key": cfg.groq_api_key.get_secret_value(),
            "base_url": entorno.url,
            "timeout": entorno.timeout_s,
            # Sin los 2 reintentos del SDK: el respaldo y Strands deciden, y el turno cabe en 55 s.
            "max_retries": 0,
        },
        model_id=model_id,
        params={"max_completion_tokens": max_tokens} | extra,
    )


def _bedrock(
    cfg: Configuracion, entorno: Entorno, model_id: str, max_tokens: int, guardia: bool
) -> BedrockModel:
    """Guardrails solo en el agente y solo sobre el mensaje nuevo (`guardContent`, D24)."""
    extra = {}
    if guardia and cfg.guardrail_id:
        extra = {
            "guardrail_id": cfg.guardrail_id,
            "guardrail_version": cfg.guardrail_version,
            "guardrail_latest_message": True,
        }
    # Como en Groq: timeout de config.yaml y pocos reintentos, para que el turno quepa en los 55 s
    # que la Lambda espera al Runtime.
    tiempos = Config(read_timeout=entorno.timeout_s, connect_timeout=5, retries={"max_attempts": 2})
    return BedrockModel(
        model_id=model_id,
        region_name=entorno.region,
        boto_client_config=tiempos,
        max_tokens=max_tokens,
        **extra,
    )


def crear_modelos(cfg: Configuracion | None = None) -> Modelos:
    cfg = cfg or Configuracion()
    entorno = cfg.entorno

    def rol(r: Rol | None, guardia: bool = False) -> Model | None:
        if r is None:
            return None
        if entorno.proveedor == "bedrock":
            modelos = [_bedrock(cfg, entorno, m, r.max_tokens, guardia) for m in r.modelos]
        else:
            modelos = [_groq(cfg, entorno, m, r.max_tokens) for m in r.modelos]
        return modelos[0] if len(modelos) == 1 else ConRespaldo(modelos)

    def auxiliar(r: Rol | None) -> Model | None:
        m = rol(r)
        return m and SinEspera(m)

    return Modelos(
        agente=rol(entorno.agente, guardia=True),
        estratega=auxiliar(entorno.estratega),
        moderador=auxiliar(entorno.moderador),
    )


class SinEspera(Model):
    """Para el estratega y el moderador: ante una cuota agotada falla al instante en vez de dejar
    que Strands espere y reintente. El turno sigue sin ellos (sin tarjeta, sin moderar) y cabe en
    los 55 s que la Lambda espera al Runtime (D50)."""

    def __init__(self, modelo: Model) -> None:
        self.modelo = modelo

    def update_config(self, **model_config) -> None:
        self.modelo.update_config(**model_config)

    def get_config(self):
        return self.modelo.get_config()

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        async for evento in self.modelo.structured_output(
            output_model, prompt, system_prompt, **kwargs
        ):
            yield evento

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        try:
            async for evento in self.modelo.stream(messages, tool_specs, system_prompt, **kwargs):
                yield evento
        except ModelThrottledException as e:
            raise RuntimeError(f"Cuota agotada: {e}") from e
