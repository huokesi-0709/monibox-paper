from __future__ import annotations

import tomllib

from app.config import PROJECT_ROOT


def _load_pyproject() -> dict:
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_windows_only_voice_dependencies_are_platform_marked():
    pyproject = _load_pyproject()
    voice_deps = pyproject["project"]["optional-dependencies"]["voice"]

    assert "comtypes>=1.4.16; sys_platform == 'win32'" in voice_deps
    assert "pywin32>=306; sys_platform == 'win32'" in voice_deps
    assert "comtypes>=1.4.16" not in voice_deps


def test_default_dependencies_stay_minimal():
    pyproject = _load_pyproject()
    deps = set(pyproject["project"]["dependencies"])
    optional = pyproject["project"]["optional-dependencies"]
    dev = set(pyproject["project"]["optional-dependencies"]["dev"])

    assert {
        "numpy>=2.0",
        "openai>=2.41",
        "psutil>=6.0.0",
        "pydantic>=2.0",
        "pydantic-settings>=2.0",
        "python-dotenv>=1.0.1",
        "pyyaml>=6.0",
        "sentence-transformers>=5",
        "soundfile>=0.12.1",
        "sqlite-vec>=0.1.6",
    } <= deps
    assert "fastapi>=0.115.0" in optional["api"]
    assert "uvicorn>=0.30.0" in optional["api"]
    assert "pytest>=9.0.0" in dev
    assert "ruff>=0.15.11" in dev
    assert "json5>=0.14" in optional["json"]
    assert "numpy>=2.0" in optional["voice"]
