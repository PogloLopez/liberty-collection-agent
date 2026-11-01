"""Sin key real ni red: `.env` en tmp_path y una key falsa; nunca se llama a la API."""

import pytest

from agil.agente import config


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    for var in ("GROQ_API_KEY", "LLM_PROVIDER", "VAR_A", "VAR_B", "VAR_C", "VAR_D"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path / ".env"


def test_cargar_env_sin_archivo_no_falla(env):
    config._cargar_env()
    assert "VAR_A" not in config.os.environ


def test_cargar_env_quita_comillas_e_ignora_comentarios(env, monkeypatch):
    env.write_text(
        "# comentario\nVAR_A=\"doble\"\nVAR_B='simple'\n  VAR_C = con espacios  \n\n#VAR_D=no\n",
        encoding="utf-8",
    )
    config._cargar_env()
    entorno = config.os.environ
    assert (entorno["VAR_A"], entorno["VAR_B"], entorno["VAR_C"]) == (
        "doble",
        "simple",
        "con espacios",
    )
    assert "VAR_D" not in entorno and "# comentario" not in entorno


def test_cargar_env_no_pisa_variables(env, monkeypatch):
    monkeypatch.setenv("VAR_A", "de_la_shell")
    env.write_text("VAR_A=del_archivo\n", encoding="utf-8")
    config._cargar_env()
    assert config.os.environ["VAR_A"] == "de_la_shell"


def test_crear_modelos_sin_key_lanza_runtime_error(env):
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        config.crear_modelos()


def test_crear_modelos_con_otro_proveedor_no_implementado(env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "otro")
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    with pytest.raises(NotImplementedError):
        config.crear_modelos()


def test_crear_modelos_construye_los_tres_sin_llamar(env, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    m = config.crear_modelos()
    ids = [x.get_config()["model_id"] for x in (m.agente, m.estratega, m.moderador)]
    assert ids == [config.AGENTE, config.ESTRATEGA, config.MODERADOR]
