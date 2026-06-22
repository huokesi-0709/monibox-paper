from __future__ import annotations

from types import SimpleNamespace

import pytest

import benchmarks.run_eval as run_eval_mod
from benchmarks.ablations import ABLATION_NAMES, get_ablation_config
from benchmarks.baselines import METHOD_CONFIGS, get_method_config

EXPECTED_METHODS = {
    "baseline",
    "rule-only",
    "vanilla-rag",
    "rag-guard",
    "hsc-rag-manual",
    "hsc-rag-de",
}


def test_method_configs_include_expected_methods():
    assert EXPECTED_METHODS.issubset(METHOD_CONFIGS)


def test_hsc_rag_de_config_is_full_paper_method():
    config = get_method_config("hsc-rag-de")

    assert config.use_input_normalization is True
    assert config.use_intent_extraction is True
    assert config.use_negation_handling is True
    assert config.use_protocol_gate is True
    assert config.use_safety_rerank is True
    assert config.use_low_evidence_routing is True
    assert config.use_safety_guard is True
    assert config.policy_path == "scoring/policy_de.json"
    assert config.disabled_modules == []


def test_hsc_rag_manual_disables_de_optimization_only():
    config = get_method_config("hsc-rag-manual")

    assert config.policy_path == "scoring/policy_manual.json"
    assert "de_optimization" in config.disabled_modules
    assert "safety_rerank" not in config.disabled_modules


def test_vanilla_rag_disables_all_hsc_safety_modules():
    config = get_method_config("vanilla-rag")

    assert config.use_input_normalization is False
    assert config.use_intent_extraction is False
    assert config.use_negation_handling is False
    assert config.use_protocol_gate is False
    assert config.use_safety_rerank is False
    assert config.use_low_evidence_routing is False
    assert config.use_safety_guard is False
    assert set(config.disabled_modules) >= {
        "input_normalization",
        "multi_intent_extraction",
        "negation_handling",
        "protocol_gate",
        "safety_rerank",
        "low_evidence_routing",
        "safety_guard",
        "de_optimization",
    }


def test_rag_guard_only_restores_safety_guard_from_vanilla_rag():
    config = get_method_config("rag-guard")

    assert config.use_safety_guard is True
    assert "safety_guard" not in config.disabled_modules
    assert set(config.disabled_modules) >= {
        "input_normalization",
        "multi_intent_extraction",
        "negation_handling",
        "protocol_gate",
        "safety_rerank",
        "low_evidence_routing",
        "de_optimization",
    }


def test_without_input_normalization_ablation():
    config = get_ablation_config("without_input_normalization")

    assert config.use_input_normalization is False
    assert "input_normalization" in config.disabled_modules


def test_without_multi_intent_is_strong_intent_extraction_ablation():
    config = get_ablation_config("without_multi_intent")

    # This is a strong ablation of risk-aware intent extraction, not only
    # secondary-intent emission.
    assert config.use_intent_extraction is False
    assert "multi_intent_extraction" in config.disabled_modules


def test_without_negation_ablation():
    config = get_ablation_config("without_negation")

    assert config.use_negation_handling is False
    assert "negation_handling" in config.disabled_modules


def test_without_protocol_gate_ablation():
    config = get_ablation_config("without_protocol_gate")

    assert config.use_protocol_gate is False
    assert "protocol_gate" in config.disabled_modules


def test_without_safety_rerank_ablation_uses_vector_only_policy(monkeypatch):
    config = get_ablation_config("without_safety_rerank")
    fake_session = SimpleNamespace(
        rt=SimpleNamespace(low_evidence_mode=None), rag=SimpleNamespace(hsc_policy=None)
    )

    monkeypatch.setattr(
        run_eval_mod,
        "load_runtime_config",
        lambda profile: SimpleNamespace(
            low_evidence_mode=True,
            rewrite_low_evidence_enabled=False,
            tts_backend="",
            rag_db_path="build/rag.db",
        ),
    )
    monkeypatch.setattr(
        run_eval_mod, "MoniSession", lambda *args, **kwargs: fake_session
    )

    session = run_eval_mod._create_session("paper_eval", config, config.policy_path)

    assert config.use_safety_rerank is False
    assert "safety_rerank" in config.disabled_modules
    assert session.rag.hsc_policy is run_eval_mod.VECTOR_ONLY_POLICY


def test_without_low_evidence_ablation():
    config = get_ablation_config("without_low_evidence")

    assert config.use_low_evidence_routing is False
    assert "low_evidence_routing" in config.disabled_modules


def test_without_guard_ablation():
    config = get_ablation_config("without_guard")

    assert config.use_safety_guard is False
    assert "safety_guard" in config.disabled_modules


def test_without_de_optimization_ablation_uses_manual_policy():
    config = get_ablation_config("without_de_optimization")

    assert config.policy_path == "scoring/policy_manual.json"
    assert "de_optimization" in config.disabled_modules


def test_unknown_method_and_ablation_raise_with_known_options():
    with pytest.raises(ValueError, match="baseline"):
        get_method_config("unknown-method")

    with pytest.raises(ValueError, match="without_guard"):
        get_ablation_config("unknown-ablation")


def test_ablation_names_are_stable():
    assert {
        "without_input_normalization",
        "without_multi_intent",
        "without_negation",
        "without_protocol_gate",
        "without_safety_rerank",
        "without_low_evidence",
        "without_guard",
        "without_de_optimization",
    } == ABLATION_NAMES
