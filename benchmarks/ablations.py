from __future__ import annotations

from dataclasses import replace

from benchmarks.baselines import MethodConfig, get_method_config

ABLATION_NAMES = {
    "without_input_normalization",
    "without_multi_intent",
    "without_negation",
    "without_protocol_gate",
    "without_safety_rerank",
    "without_low_evidence",
    "without_guard",
    "without_de_optimization",
}


def get_ablation_config(name: str) -> MethodConfig:
    base = get_method_config("hsc-rag-de")
    if name == "without_input_normalization":
        return replace(base, name=name, use_input_normalization=False)
    if name == "without_multi_intent":
        return replace(base, name=name, use_intent_extraction=False)
    if name == "without_negation":
        return replace(base, name=name, use_negation_handling=False)
    if name == "without_protocol_gate":
        return replace(base, name=name, use_protocol_gate=False)
    if name == "without_safety_rerank":
        return replace(base, name=name, use_safety_rerank=False)
    if name == "without_low_evidence":
        return replace(base, name=name, use_low_evidence_routing=False)
    if name == "without_guard":
        return replace(base, name=name, use_safety_guard=False)
    if name == "without_de_optimization":
        return replace(base, name=name, policy_path="scoring/policy_manual.json")

    known = ", ".join(sorted(ABLATION_NAMES))
    raise ValueError(f"unknown ablation '{name}', expected one of: {known}")
