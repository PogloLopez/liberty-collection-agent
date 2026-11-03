"""Sin key real ni red: `.env` en tmp_path y una key falsa; nunca se llama a la API."""

import asyncio

import pytest
from conftest import ModeloGuionado
from pydantic import ValidationError
from strands.types.exceptions import ContextWindowOverflowException, ModelThrottledException

from agil.agente import config


@pytest.fixture
def env(tmp_path, monkeypatch):
    for var in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY_PARAM", "LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path / ".env"


def _cfg(env, **kwargs):
    return config.Configuracion(_env_file=env, **kwargs)


# config.yaml ya no trae sección de Groq (D51): los tests que la usan la pasan aquí.
DEV_GROQ = config.Entorno(
    proveedor="groq",
    url="https://api.groq.com/openai/v1",
    timeout_s=20,
    agente=config.Rol(modelos=["openai/gpt-oss-120b"], max_tokens=64),
)


def test_sin_key_falla_al_construir_la_configuracion(env):
    with pytest.raises(ValidationError, match="OPENROUTER_API_KEY"):
        _cfg(env)


def test_la_key_no_se_imprime(env):
    env.write_text('OPENROUTER_API_KEY="clave-falsa"\n', encoding="utf-8")
    cfg = _cfg(env)
    assert cfg.api_key.get_secret_value() == "clave-falsa"
    assert "clave-falsa" not in repr(cfg)


def test_la_variable_de_entorno_pisa_al_env(env, monkeypatch):
    env.write_text("OPENROUTER_API_KEY=del_archivo\n", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "de_la_shell")
    assert _cfg(env).api_key.get_secret_value() == "de_la_shell"


def test_yaml_sin_una_seccion_por_proveedor_falla(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    dev = _cfg(env).dev
    with pytest.raises(ValidationError, match="una sola sección"):
        config.Configuracion(_env_file=env, dev=dev, prod=dev)


def test_nube_con_guardrails_solo_en_el_agente(env, monkeypatch):
    """Sin red: el modelo de Bedrock se sustituye por uno que solo guarda sus argumentos."""
    creados = []
    monkeypatch.setattr(config, "BedrockModel", lambda **kw: creados.append(kw) or kw)
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("GUARDRAIL_ID", "gr-1")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")
    m = config.crear_modelos(_cfg(env))
    assert m.agente["model_id"] == "us.amazon.nova-lite-v1:0"
    assert m.agente["region_name"] == "us-east-1"
    assert m.agente["guardrail_id"] == "gr-1" and m.agente["guardrail_latest_message"] is True
    assert isinstance(m.estratega, config.SinEspera)  # D50: el auxiliar no espera cuotas
    assert m.estratega.modelo["model_id"] == "us.amazon.nova-micro-v1:0"
    assert "guardrail_id" not in m.estratega.modelo and m.moderador is None
    assert len(creados) == 2


def test_crear_modelos_desde_el_yaml_sin_llamar(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    cfg = _cfg(env)
    assert cfg.entorno.url.startswith("https://openrouter.ai") and cfg.entorno.agente.max_tokens
    m = config.crear_modelos(cfg)
    assert isinstance(m.agente, config.ConRespaldo)
    assert [x.get_config()["model_id"] for x in m.agente.modelos] == [
        "anthropic/claude-haiku-5.5",
        "openai/gpt-oss-120b",
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


def test_cuota_por_minuto_pasa_al_siguiente_y_en_el_ultimo_se_espera():  # D50, D41
    error = ModelThrottledException("429 Rate limit reached on tokens per minute (TPM)")
    siguiente = ModeloGuionado("Hola.")
    assert _texto(config.ConRespaldo([_Falla(error), siguiente])) == "Hola."
    with pytest.raises(ModelThrottledException):
        _texto(config.ConRespaldo([ModeloGuionado(""), _Falla(error)]))


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
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    monkeypatch.setenv("MODO_DEMO", str(valor).lower())
    assert _cfg(env).modo_demo is valor


def test_cuota_diaria_pasa_al_siguiente_modelo():
    diaria = ModelThrottledException("429 Rate limit reached on tokens per day (TPD)")
    siguiente = ModeloGuionado("Hola.")
    assert _texto(config.ConRespaldo([_Falla(diaria), siguiente])) == "Hola."


def test_razonamiento_por_familia_de_modelo(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    cfg = _cfg(env)
    m = config.crear_modelos(cfg).agente.modelos
    assert m[0].get_config()["params"] == {"max_completion_tokens": 1500}  # Claude: sin razonar
    assert m[1].get_config()["params"]["reasoning_effort"] == "low"
    qwen = config._compatible(cfg, cfg.entorno, "qwen/qwen3.8-27b", 64).get_config()["params"]
    assert qwen["extra_body"] == {"reasoning_format": "hidden"} and "reasoning_effort" not in qwen


def test_parametros_que_acepta_el_sdk_de_openai(env, monkeypatch):
    """D50: `reasoning_format` como argumento directo rompía `create()` con TypeError antes de
    llamar a Groq, y el respaldo qwen nunca respondía. Todo parámetro que pasamos debe existir en
    la firma del SDK (lo propio de Groq va en `extra_body`)."""
    import inspect

    from openai.resources.chat.completions import AsyncCompletions

    aceptados = set(inspect.signature(AsyncCompletions.create).parameters)
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    modelos = config.crear_modelos(_cfg(env))
    for rol in (modelos.agente, modelos.estratega, modelos.moderador):
        if rol is None:  # estratega y moderador son opcionales
            continue
        rol = getattr(rol, "modelo", rol)  # SinEspera envuelve a los auxiliares
        for m in getattr(rol, "modelos", [rol]):  # ConRespaldo trae varios
            desconocidos = set(m.get_config()["params"]) - aceptados
            assert not desconocidos, (m.get_config()["model_id"], desconocidos)


def test_modelo_sin_familia_conocida_no_recibe_razonamiento(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    cfg = _cfg(env)
    params = config._compatible(cfg, cfg.entorno, "llama-3.3-70b-versatile", 64).get_config()[
        "params"
    ]
    assert params == {"max_completion_tokens": 64}


def test_en_la_nube_la_key_sale_del_parametro(env, monkeypatch):  # D50, D51, sin red
    leidos = []
    monkeypatch.setattr(
        config, "leer_parametro", lambda nombre, region: leidos.append((nombre, region)) or "k"
    )
    monkeypatch.setenv("LLM_API_KEY_PARAM", "/agil/openrouter-api-key")
    cfg = _cfg(env)
    assert cfg.api_key.get_secret_value() == "k"
    assert leidos == [("/agil/openrouter-api-key", cfg.prod.region)]


def test_con_key_no_se_lee_el_parametro(env, monkeypatch):
    monkeypatch.setattr(config, "leer_parametro", lambda *a: pytest.fail("no debía leer"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    monkeypatch.setenv("LLM_API_KEY_PARAM", "/agil/openrouter-api-key")
    assert _cfg(env).api_key.get_secret_value() == "clave-falsa"


def test_groq_sin_key_ni_parametro_falla(env, monkeypatch):  # aunque haya key de OpenRouter
    monkeypatch.setattr(config, "leer_parametro", lambda *a: pytest.fail("no debía leer"))
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        _cfg(env, dev=DEV_GROQ)


def test_sin_espera_convierte_la_cuota_en_error_inmediato():  # D50
    cuota = ModelThrottledException("429 Rate limit reached on tokens per minute (TPM)")
    with pytest.raises(RuntimeError, match="Cuota agotada") as e:
        _texto(config.SinEspera(_Falla(cuota)))
    assert e.value.__cause__ is cuota
    with pytest.raises(TimeoutError):
        _texto(config.SinEspera(_Falla()))
    assert _texto(config.SinEspera(ModeloGuionado("Hola."))) == "Hola."


def test_compatible_sin_reintentos_del_sdk(env, monkeypatch):  # D50
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-falsa")
    cfg = _cfg(env)
    assert (
        config._compatible(cfg, cfg.entorno, "openai/gpt-oss-20b", 64).client_args["max_retries"]
        == 0
    )


def test_api_key_es_la_del_proveedor_elegido(env, monkeypatch):  # D51
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "de-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "de-openrouter")
    assert _cfg(env, dev=DEV_GROQ).api_key.get_secret_value() == "de-groq"
