from __future__ import annotations

import tomllib

from app.config import PROJECT_ROOT


def _load_pyproject() -> dict:
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())


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

    assert deps == set()
    assert "json5>=0.14" in optional["json"]
    assert "python-dotenv>=1.0.1" in optional["env"]
    assert "numpy>=2.0" in optional["voice"]
    assert "numpy>=2.0" in optional["knowledge"]
    assert "sqlite-vec>=0.1.6" in optional["knowledge"]
    assert "psutil>=6.0.0" in optional["perf"]
    assert "soundfile>=0.12.1" in optional["tools"]
