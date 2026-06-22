from __future__ import annotations

from dataclasses import dataclass

from benchmarks.schema import BenchmarkCase


@dataclass(frozen=True)
class MethodConfig:
    """Static benchmark method switches for paper evaluation.

    The `baseline` and `rule-only` methods intentionally use
    `baseline_reply(case)`, which reads expected labels from the benchmark
    case. They are deterministic smoke/oracle-label template baselines, not
    fair deployed-system baselines.
    """

    name: str
    use_input_normalization: bool
    use_intent_extraction: bool
    use_negation_handling: bool
    use_protocol_gate: bool
    use_safety_rerank: bool
    use_low_evidence_routing: bool
    use_safety_guard: bool
    policy_path: str | None
    llm_backend: str = "null"

    @property
    def disabled_modules(self) -> list[str]:
        disabled: list[str] = []
        if not self.use_input_normalization:
            disabled.append("input_normalization")
        if not self.use_intent_extraction:
            disabled.append("multi_intent_extraction")
        if not self.use_negation_handling:
            disabled.append("negation_handling")
        if not self.use_protocol_gate:
            disabled.append("protocol_gate")
        if not self.use_safety_rerank:
            disabled.append("safety_rerank")
        if not self.use_low_evidence_routing:
            disabled.append("low_evidence_routing")
        if not self.use_safety_guard:
            disabled.append("safety_guard")
        if self.policy_path != "scoring/policy_de.json":
            disabled.append("de_optimization")
        return disabled


METHOD_CONFIGS: dict[str, MethodConfig] = {
    "baseline": MethodConfig(
        name="baseline",
        use_input_normalization=True,
        use_intent_extraction=True,
        use_negation_handling=True,
        use_protocol_gate=True,
        use_safety_rerank=False,
        use_low_evidence_routing=False,
        use_safety_guard=True,
        policy_path=None,
    ),
    "rule-only": MethodConfig(
        name="rule-only",
        use_input_normalization=True,
        use_intent_extraction=True,
        use_negation_handling=True,
        use_protocol_gate=True,
        use_safety_rerank=False,
        use_low_evidence_routing=False,
        use_safety_guard=True,
        policy_path=None,
    ),
    "vanilla-rag": MethodConfig(
        name="vanilla-rag",
        use_input_normalization=False,
        use_intent_extraction=False,
        use_negation_handling=False,
        use_protocol_gate=False,
        use_safety_rerank=False,
        use_low_evidence_routing=False,
        use_safety_guard=False,
        policy_path=None,
    ),
    "rag-guard": MethodConfig(
        name="rag-guard",
        use_input_normalization=False,
        use_intent_extraction=False,
        use_negation_handling=False,
        use_protocol_gate=False,
        use_safety_rerank=False,
        use_low_evidence_routing=False,
        use_safety_guard=True,
        policy_path=None,
    ),
    "hsc-rag-manual": MethodConfig(
        name="hsc-rag-manual",
        use_input_normalization=True,
        use_intent_extraction=True,
        use_negation_handling=True,
        use_protocol_gate=True,
        use_safety_rerank=True,
        use_low_evidence_routing=True,
        use_safety_guard=True,
        policy_path="scoring/policy_manual.json",
    ),
    "hsc-rag-de": MethodConfig(
        name="hsc-rag-de",
        use_input_normalization=True,
        use_intent_extraction=True,
        use_negation_handling=True,
        use_protocol_gate=True,
        use_safety_rerank=True,
        use_low_evidence_routing=True,
        use_safety_guard=True,
        policy_path="scoring/policy_de.json",
    ),
}


def get_method_config(name: str) -> MethodConfig:
    try:
        return METHOD_CONFIGS[name]
    except KeyError as exc:
        known = ", ".join(sorted(METHOD_CONFIGS))
        raise ValueError(
            f"unknown benchmark method '{name}', expected one of: {known}"
        ) from exc


def baseline_reply(case: BenchmarkCase) -> str:
    """Deterministic oracle-label template reply for smoke evaluation.

    This function uses `case.expected_primary_intent`; it should be reported as
    an oracle-label template baseline rather than a realistic model baseline.
    """

    query = case.query.strip()
    if not query:
        return ""
    if case.expected_primary_intent == "severe_bleeding":
        return "先用干净布料直接按压出血处，减少活动。"
    if case.expected_primary_intent == "respiratory_distress":
        return "先减少说话，保持能呼吸的姿势，慢慢呼吸。"
    if case.expected_primary_intent == "trapped_or_crush":
        return "先别硬挣扎，保存体力，留意呼吸和出血。"
    if case.expected_primary_intent == "out_of_scope":
        return "这不是应急求助问题，请说身体受伤或被困情况。"
    return "请先保持冷静，减少活动，描述最严重的问题。"
