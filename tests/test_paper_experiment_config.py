from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

from app.config import PROJECT_ROOT
from app.settings import load_settings
from language.backends import NullLLMBackend, create_llm_backend
from runtime.runtime_config import load_runtime_config


SCRIPT_NAMES = [
    "run_clean_eval.sh",
    "run_robust_eval.sh",
    "run_de_optimize.sh",
    "run_ablation.sh",
    "export_tables.sh",
]


def test_paper_eval_profile_loads_as_offline_deterministic_config(monkeypatch):
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_GGUF_PATH", raising=False)
    settings = load_settings("paper_eval")
    cfg = load_runtime_config("paper_eval")

    assert settings.app.mode == "text"
    assert settings.debug.runtime_trace_enabled is True
    assert settings.debug.trace_path == "build/eval/traces/paper_eval_trace.jsonl"
    assert cfg.llm_backend == "null"
    assert cfg.llm_temperature == 0.0
    assert cfg.llm_stream is False
    assert cfg.rewrite_enabled is False
    assert cfg.rewrite_protocol_enabled is False
    assert cfg.rewrite_low_evidence_enabled is False
    assert cfg.tts_backend == ""
    assert cfg.enable_led is False
    assert cfg.enable_screen is False


def test_paper_eval_null_backend_ignores_deepseek_key(monkeypatch):
    monkeypatch.setenv("RUNTIME_PROFILE", "paper_eval")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "paper-profile-offline-key")
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_GGUF_PATH", raising=False)

    backend = create_llm_backend()

    assert isinstance(backend, NullLLMBackend)
    assert backend.backend_name == "null"


def test_monibox_eval_entry_point_imports():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    entry = pyproject["project"]["scripts"]["monibox-eval"]
    module_name, function_name = entry.split(":")

    module = importlib.import_module(module_name)

    assert callable(getattr(module, function_name))

    de_entry = pyproject["project"]["scripts"]["monibox-de"]
    de_module_name, de_function_name = de_entry.split(":")
    de_module = importlib.import_module(de_module_name)

    assert callable(getattr(de_module, de_function_name))
    assert pyproject["project"]["optional-dependencies"]["paper"] == [
        "pymoo>=0.6.1.6",
        "pandas>=2",
        "matplotlib>=3",
    ]


def test_paper_scripts_exist_and_use_relative_paths():
    scripts_dir = PROJECT_ROOT / "scripts"
    for script_name in SCRIPT_NAMES:
        script = scripts_dir / script_name
        text = script.read_text(encoding="utf-8")

        assert script.exists()
        assert "profiles/paper_eval.yaml" in text
        assert "build/eval" in text
        assert "D:\\" not in text
        assert "/home/" not in text
        assert not any(Path(part).is_absolute() for part in text.split())
