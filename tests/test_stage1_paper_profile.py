from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT
from benchmarks.run_eval import _profile_name
from runtime.runtime_config import _ENV_FIELD_MAP, load_runtime_config

PAPER_PROFILE = PROJECT_ROOT / "profiles" / "paper_eval.yaml"


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_key in _ENV_FIELD_MAP:
        monkeypatch.delenv(env_key, raising=False)
    for env_key in [
        "ALLOW_PAPER_ENV_OVERRIDE",
        "LLM__BACKEND",
        "LLM__TEMPERATURE",
        "REWRITE__ENABLED",
        "SPEECH__TTS__BACKEND",
        "HARDWARE__ENABLE_LED",
        "HARDWARE__ENABLE_SCREEN",
    ]:
        monkeypatch.delenv(env_key, raising=False)


def test_paper_eval_profile_exists() -> None:
    assert PAPER_PROFILE.exists(), (
        "profiles/paper_eval.yaml is required as the paper reproduction contract."
    )


def test_paper_eval_runtime_config_is_offline_and_traceable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)

    cfg = load_runtime_config("paper_eval")

    assert cfg.llm_backend in {"null", "none", "disabled", "off", ""}
    assert cfg.llm_temperature == 0.0
    assert cfg.llm_stream is False
    assert cfg.rewrite_enabled is False
    assert cfg.rewrite_protocol_enabled is False
    assert cfg.rewrite_low_evidence_enabled is False
    assert cfg.tts_backend == ""
    assert cfg.enable_led is False
    assert cfg.enable_screen is False
    assert cfg.runtime_trace_enabled is True
    assert cfg.trace_path.startswith("build/eval/")


def test_missing_profile_file_fails_instead_of_falling_back() -> None:
    missing = "profiles/does_not_exist_for_stage1.yaml"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        _profile_name(None, missing)


def test_profile_file_must_be_under_profiles_directory(tmp_path: Path) -> None:
    profile_file = tmp_path / "paper_eval.yaml"
    profile_file.write_text("app:\n  mode: text\n", encoding="utf-8")

    with pytest.raises(ValueError, match="under profiles"):
        _profile_name(None, str(profile_file))


def test_paper_eval_ignores_local_runtime_env_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("TTS_BACKEND", "sherpa")
    monkeypatch.setenv("REWRITE_ENABLED", "true")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.8")
    monkeypatch.setenv("LLM__BACKEND", "deepseek")
    monkeypatch.setenv("SPEECH__TTS__BACKEND", "pyttsx3")
    monkeypatch.setenv("HARDWARE__ENABLE_LED", "true")
    monkeypatch.setenv("HARDWARE__ENABLE_SCREEN", "true")

    cfg = load_runtime_config("paper_eval")

    assert cfg.tts_backend == ""
    assert cfg.rewrite_enabled is False
    assert cfg.llm_temperature == 0.0
    assert cfg.llm_backend == "null"
    assert cfg.enable_led is False
    assert cfg.enable_screen is False


def test_non_paper_profiles_keep_legacy_runtime_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("TTS_MAX_CHARS", "55")

    cfg = load_runtime_config("voice_mvp")

    assert cfg.tts_max_chars == 55
