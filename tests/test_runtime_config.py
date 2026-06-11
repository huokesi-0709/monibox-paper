from app.config import PROJECT_ROOT
from runtime.runtime_config import (
    _ENV_FIELD_MAP,
    _resolve_profile_path,
    load_runtime_config,
)


def _clear_runtime_env(monkeypatch):
    for env_key in _ENV_FIELD_MAP:
        monkeypatch.delenv(env_key, raising=False)


def test_profile_names_resolve_to_profiles_directory(monkeypatch):
    monkeypatch.delenv("RUNTIME_CONFIG_PATH", raising=False)
    monkeypatch.delenv("RUNTIME_PROFILE", raising=False)

    path = _resolve_profile_path("voice_mvp")

    assert path == PROJECT_ROOT / "profiles" / "voice_mvp.yaml"
    assert path.exists()


def test_profile_values_override_runtime_defaults(monkeypatch):
    monkeypatch.delenv("RUNTIME_CONFIG_PATH", raising=False)
    _clear_runtime_env(monkeypatch)

    cfg = load_runtime_config("radxa_light")

    assert cfg.tts_max_chars == 68
    assert cfg.llm_ctx == 1024
    assert cfg.rewrite_enabled is False


def test_environment_values_override_profile(monkeypatch):
    monkeypatch.delenv("RUNTIME_CONFIG_PATH", raising=False)
    monkeypatch.setenv("TTS_MAX_CHARS", "55")

    cfg = load_runtime_config("voice_mvp")

    assert cfg.tts_max_chars == 55
