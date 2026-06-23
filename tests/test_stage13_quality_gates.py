from __future__ import annotations

import tomllib

import pytest
import yaml

from app.config import PROJECT_ROOT


@pytest.mark.paper
def test_stage13_quality_gate_files_exist():
    paths = [
        PROJECT_ROOT / "scripts" / "run_tests.sh",
        PROJECT_ROOT / ".github" / "workflows" / "ci.yml",
        PROJECT_ROOT / "docs" / "stage13_test_system.md",
        PROJECT_ROOT / "docs" / "test_matrix.md",
        PROJECT_ROOT / "profiles" / "paper_eval.yaml",
        PROJECT_ROOT / "paper" / "README.md",
        PROJECT_ROOT / "paper" / "manuscript_zh.md",
        PROJECT_ROOT / "paper" / "reproducibility.md",
    ]

    for path in paths:
        assert path.exists(), f"missing stage 13 quality gate file: {path}"


@pytest.mark.paper
def test_core_stage_documents_exist():
    docs = [
        "stage0_reproducibility_checklist.md",
        "stage1_paper_profile.md",
        "stage2_input_normalization.md",
        "stage3_intent_extraction.md",
        "stage4_protocol_matching.md",
        "stage5_hsc_rag_rerank.md",
        "stage6_paper_trace.md",
        "stage7_benchmark_eval.md",
        "stage8_robustness_generator.md",
        "stage9_baselines_ablations.md",
        "stage10_de_optimization.md",
        "stage11_export_tables.md",
        "stage12_paper_draft.md",
        "stage13_test_system.md",
    ]

    for name in docs:
        assert (PROJECT_ROOT / "docs" / name).exists(), f"missing docs/{name}"


@pytest.mark.paper
def test_de_config_does_not_use_test_paths():
    config = yaml.safe_load(
        (PROJECT_ROOT / "experiments" / "configs" / "de_hsc_rag.yaml").read_text(
            encoding="utf-8"
        )
    )

    for key in ("clean_dev_path", "robustness_dev_path"):
        value = str(config[key]).replace("\\", "/").lower()
        assert "test" not in value


@pytest.mark.paper
def test_pyproject_pytest_configuration_declares_testpaths_and_markers():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    pytest_options = pyproject["tool"]["pytest"]["ini_options"]

    assert pytest_options["testpaths"] == ["tests"]
    markers = "\n".join(pytest_options["markers"])
    assert "unit:" in markers
    assert "integration:" in markers
    assert "paper:" in markers
    assert "slow:" in markers


@pytest.mark.paper
def test_run_tests_script_is_lightweight():
    script = (PROJECT_ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8")
    forbidden = [
        "run_de_optimize.sh",
        "run_clean_eval.sh",
        "run_robust_eval.sh",
        "run_ablation.sh",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
    ]

    assert "python -m pytest" in script
    for token in forbidden:
        assert token not in script


@pytest.mark.paper
def test_ci_workflow_is_lightweight_and_secret_free():
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    lowered = workflow.lower()
    forbidden = [
        "openai_api_key",
        "deepseek_api_key",
        "hardware",
        "tts",
        "run_de_optimize.sh",
        "run_clean_eval.sh",
        "run_robust_eval.sh",
        "run_ablation.sh",
        "scripts/export_tables.sh",
    ]

    assert "python -m pytest" in workflow
    assert "ruff check" in workflow
    for token in forbidden:
        assert token not in lowered


@pytest.mark.paper
def test_paper_eval_profile_keeps_remote_voice_and_hardware_disabled():
    profile = yaml.safe_load(
        (PROJECT_ROOT / "profiles" / "paper_eval.yaml").read_text(encoding="utf-8")
    )

    llm = profile["llm"]
    tts = profile["speech"]["tts"]
    hardware = profile["hardware"]

    assert llm.get("backend") in (None, "", "null", "none", "disabled")
    assert float(llm.get("temperature")) == 0.0
    assert bool(llm.get("stream")) is False
    assert tts.get("backend") in ("", None, "disabled", "none", "null")
    assert hardware.get("enable_led") is False
    assert hardware.get("enable_screen") is False
    assert hardware.get("enable_precomputed_audio") is False
