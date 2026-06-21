from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PAPER_PROFILE = PROJECT_ROOT / "profiles" / "paper_eval.yaml"

REQUIRED_PAPER_SCRIPTS = [
    PROJECT_ROOT / "scripts" / "run_clean_eval.sh",
    PROJECT_ROOT / "scripts" / "run_robust_eval.sh",
    PROJECT_ROOT / "scripts" / "run_de_optimize.sh",
    PROJECT_ROOT / "scripts" / "run_ablation.sh",
    PROJECT_ROOT / "scripts" / "export_tables.sh",
]

REQUIRED_BENCHMARK_DATA = [
    PROJECT_ROOT / "benchmarks" / "data" / "clean_dev.jsonl",
    PROJECT_ROOT / "benchmarks" / "data" / "robustness_dev.jsonl",
]

DISABLED_BACKEND_VALUES = {None, "", "null", "none", "disabled", "off", False}


def _load_paper_profile() -> dict[str, Any]:
    assert PAPER_PROFILE.exists(), (
        "Stage 0 paper contract broken: profiles/paper_eval.yaml is missing."
    )
    data = yaml.safe_load(PAPER_PROFILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict), (
        "Stage 0 paper contract broken: profiles/paper_eval.yaml must parse "
        "as a YAML mapping."
    )
    return data


def _nested_get(data: dict[str, Any], dotted_key: str) -> Any:
    current: Any = data
    for key in dotted_key.split("."):
        assert isinstance(current, dict) and key in current, (
            f"Stage 0 paper contract broken: missing `{dotted_key}` in "
            "profiles/paper_eval.yaml."
        )
        current = current[key]
    return current


def test_paper_eval_profile_exists() -> None:
    assert PAPER_PROFILE.exists(), (
        "Stage 0 paper contract broken: profiles/paper_eval.yaml is required "
        "for paper reproduction."
    )


def test_paper_eval_profile_keeps_offline_deterministic_settings() -> None:
    profile = _load_paper_profile()

    llm_backend = _nested_get(profile, "llm.backend")
    assert llm_backend in DISABLED_BACKEND_VALUES, (
        "Stage 0 paper contract broken: llm.backend must stay disabled in "
        f"profiles/paper_eval.yaml, got {llm_backend!r}."
    )

    temperature = _nested_get(profile, "llm.temperature")
    assert temperature == 0.0, (
        "Stage 0 paper contract broken: llm.temperature must be 0.0 for "
        f"deterministic paper evaluation, got {temperature!r}."
    )

    rewrite_enabled = _nested_get(profile, "rewrite.enabled")
    assert rewrite_enabled is False, (
        "Stage 0 paper contract broken: rewrite.enabled must be false for "
        f"the paper profile, got {rewrite_enabled!r}."
    )

    tts_backend = _nested_get(profile, "speech.tts.backend")
    assert tts_backend in DISABLED_BACKEND_VALUES, (
        "Stage 0 paper contract broken: speech.tts.backend must stay empty "
        f"or disabled for paper evaluation, got {tts_backend!r}."
    )

    enable_led = _nested_get(profile, "hardware.enable_led")
    assert enable_led is False, (
        "Stage 0 paper contract broken: hardware.enable_led must be false "
        f"for paper evaluation, got {enable_led!r}."
    )

    enable_screen = _nested_get(profile, "hardware.enable_screen")
    assert enable_screen is False, (
        "Stage 0 paper contract broken: hardware.enable_screen must be false "
        f"for paper evaluation, got {enable_screen!r}."
    )

    runtime_trace_enabled = _nested_get(profile, "debug.runtime_trace_enabled")
    assert runtime_trace_enabled is True, (
        "Stage 0 paper contract broken: debug.runtime_trace_enabled must be "
        f"true so offline eval traces remain auditable, got {runtime_trace_enabled!r}."
    )


def test_stage0_paper_experiment_scripts_exist() -> None:
    missing = [
        str(path.relative_to(PROJECT_ROOT))
        for path in REQUIRED_PAPER_SCRIPTS
        if not path.exists()
    ]

    assert not missing, (
        "Stage 0 paper contract broken: missing paper experiment script(s): "
        + ", ".join(missing)
    )


def test_stage0_benchmark_data_entrypoints_exist() -> None:
    missing = [
        str(path.relative_to(PROJECT_ROOT))
        for path in REQUIRED_BENCHMARK_DATA
        if not path.exists()
    ]

    assert not missing, (
        "Stage 0 paper contract broken: missing benchmark data entrypoint(s): "
        + ", ".join(missing)
    )
