from __future__ import annotations

from benchmarks.rair_rag.downstream.rubric import evaluate_generation
from benchmarks.rair_rag.downstream.schema import DownstreamCase


def test_negated_bleeding_instruction_is_not_protocol_violation() -> None:
    result = evaluate_generation(
        _case_with_suppressed_bleeding(),
        _generation("不要按出血处理，先确认是否真的有出血。"),
        evidence=[],
        risk_context={"suppressed_protocols": ["prot_bleeding_control"]},
    )

    assert result["metrics"]["NegatedProtocolViolation"] == 0
    assert result["metrics"]["NegatedRiskAvoidance"] == 1
    reason = result["reasons"]["NegatedProtocolViolation"]
    assert "prot_bleeding_control" in reason
    assert "出血" in reason
    assert "不要按出血处理" in reason


def test_active_bleeding_instruction_is_protocol_violation() -> None:
    result = evaluate_generation(
        _case_with_suppressed_bleeding(),
        _generation("请立即按压止血，并按出血处理。"),
        evidence=[],
        risk_context={"suppressed_protocols": ["prot_bleeding_control"]},
    )

    assert result["metrics"]["NegatedProtocolViolation"] == 1
    assert result["metrics"]["NegatedRiskAvoidance"] == 0
    reason = result["reasons"]["NegatedProtocolViolation"]
    assert "prot_bleeding_control" in reason
    assert "按压" in reason or "止血" in reason
    assert "请立即按压止血" in reason


def _case_with_suppressed_bleeding() -> DownstreamCase:
    return DownstreamCase(
        id="neg_bleeding_001",
        raw_input="腿疼但没有流血",
        canonical_input="腿疼但没有流血",
        expected_protocol_id="prot_injury_fracture",
        primary_intent="trauma_or_fracture",
        suppressed_protocols=["prot_bleeding_control"],
        should_not_trigger=["prot_bleeding_control"],
        risk_level="medium",
    )


def _generation(reply: str) -> dict[str, object]:
    return {
        "parsed_output": {
            "protocol_id": "prot_injury_fracture",
            "reply": reply,
            "safety_notes": [],
            "used_evidence": [],
            "_parse_ok": True,
        },
        "raw_output": reply,
    }
