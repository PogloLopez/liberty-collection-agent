"""Sin key real ni red: `.env` en tmp_path y una key falsa; nunca se llama a la API."""

import asyncio

import pytest
from conftest import ModeloGuionado
from pydantic import ValidationError
from strands.types.exceptions import ContextWindowOverflowException

from agil.agente import config


@pytest.fixture
def env(tmp_path, monkeypatch):
    for var in ("GROQ_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path / ".env"


def _cfg(env):
    return config.Configuracion(_env_file=env)


def test_sin_key_falla_al_construir_la_configuracion(env):
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        _cfg(env)


def test_la_key_no_se_imprime(env):
    env.write_text('GROQ_API_KEY="clave-falsa"\n', encoding="utf-8")
    cfg = _cfg(env)
    assert cfg.groq_api_key.get_secret_value() == "clave-falsa"
    assert "clave-falsa" not in repr(cfg)


def test_la_variable_de_entorno_pisa_al_env(env, monkeypatch):
    env.write_text("GROQ_API_KEY=del_archivo\n", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "de_la_shell")
    assert _cfg(env).groq_api_key.get_secret_value() == "de_la_shell"


def test_yaml_sin_una_seccion_por_proveedor_falla(env, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    dev = _cfg(env).dev
    with pytest.raises(ValidationError, match="una sola sección"):
        config.Configuracion(_env_file=env, dev=dev, prod=dev)


def test_proveedor_de_la_nube_no_implementado(env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    with pytest.raises(NotImplementedError):
        config.crear_modelos(_cfg(env))


def test_crear_modelos_desde_el_yaml_sin_llamar(env, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    cfg = _cfg(env)
    assert cfg.entorno.url.startswith("https://api.groq.com") and cfg.entorno.agente.max_tokens
    m = config.crear_modelos(cfg)
    assert isinstance(m.agente, config.ConRespaldo)
    assert [x.get_config()["model_id"] for x in m.agente.modelos] == [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ]
    assert m.estratega.get_config()["model_id"] == "openai/gpt-oss-20b"  # uno solo: sin envoltorio
    assert m.moderador.get_config()["model_id"] == "openai/gpt-oss-safeguard-20b"


class _Falla(ModeloGuionado):
    def __init__(self, error=TimeoutError):
        super().__init__()
        self.error = error

    async def stream(self, *args, **kwargs):
        self.recibido.append(args)
        raise self.error
        yield


def _texto(modelo) -> str:
    async def correr():
        return [e async for e in modelo.stream([], None, None)]

    eventos = asyncio.run(correr())
    return "".join(e.get("contentBlockDelta", {}).get("delta", {}).get("text", "") for e in eventos)


def test_respaldo_pasa_al_siguiente_si_falla_o_responde_vacio():
    falla, vacio, bueno = _Falla(), ModeloGuionado("  "), ModeloGuionado("Hola.")
    sobra = ModeloGuionado()
    assert _texto(config.ConRespaldo([falla, vacio, bueno, sobra])) == "Hola."
    assert len(falla.recibido) == len(vacio.recibido) == len(bueno.recibido) == 1
    assert sobra.recibido == []


def test_respaldo_relanza_el_ultimo_error_si_fallan_todos():
    with pytest.raises(TimeoutError):
        _texto(config.ConRespaldo([ModeloGuionado(""), _Falla()]))


def test_respaldo_no_cambia_de_modelo_si_se_excede_la_ventana():
    siguiente = ModeloGuionado("Hola.")
    with pytest.raises(ContextWindowOverflowException):
        _texto(config.ConRespaldo([_Falla(ContextWindowOverflowException), siguiente]))
    assert siguiente.recibido == []


def test_respaldo_acepta_una_tool_sin_texto():
    con_tool, siguiente = ModeloGuionado(("consultar_saldo", {})), ModeloGuionado("No.")
    _texto(config.ConRespaldo([con_tool, siguiente]))
    assert len(con_tool.recibido) == 1 and siguiente.recibido == []


def test_respaldo_no_prueba_alternativas_si_se_cancela():
    import threading

    cancelado, siguiente = threading.Event(), ModeloGuionado("Hola.")

    class _FallaYCancela(_Falla):
        async def stream(self, *args, **kwargs):
            cancelado.set()
            raise TimeoutError
            yield

    async def correr():
        modelo = config.ConRespaldo([_FallaYCancela(), siguiente])
        return [e async for e in modelo.stream([], None, None, cancel_signal=cancelado)]

    with pytest.raises(TimeoutError):
        asyncio.run(correr())
    assert siguiente.recibido == []


def test_respaldo_propaga_la_config_a_todos_y_lee_la_del_primero():
    class _ConConfig(ModeloGuionado):
        def __init__(self, model_id):
            super().__init__()
            self.cfg = {"model_id": model_id}

        def update_config(self, **model_config):
            self.cfg.update(model_config)

        def get_config(self):
            return self.cfg

    a, b = _ConConfig("a"), _ConConfig("b")
    respaldo = config.ConRespaldo([a, b])
    respaldo.update_config(max_tokens=7)
    assert a.cfg["max_tokens"] == b.cfg["max_tokens"] == 7
    assert respaldo.get_config()["model_id"] == "a"


@pytest.mark.parametrize("valor", [True, False])
def test_modo_demo_lo_pisa_el_entorno(env, monkeypatch, valor):
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    monkeypatch.setenv("MODO_DEMO", str(valor).lower())
    assert _cfg(env).modo_demo is valor
