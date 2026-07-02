from __future__ import annotations

import json
from pathlib import Path

from benchmarks.rair_rag.downstream.evaluate_generation_outputs import (
    evaluate_generation_outputs,
)


def test_generation_summary_breaks_down_safe_response_failures(tmp_path: Path) -> None:
    inputs = tmp_path / "outputs.jsonl"
    out = tmp_path / "evaluated.jsonl"
    summary_path = tmp_path / "summary.json"
    rows = [
        _row(
            case_id="wrong_protocol",
            risk_level="medium",
            expected_protocol_id="prot_respiratory_distress",
            primary_intent="respiratory_distress",
            parsed_protocol_id="prot_bleeding_control",
            reply="ok",
        ),
        _row(
            case_id="missing_high_risk_action",
            risk_level="critical",
            expected_protocol_id="prot_respiratory_distress",
            primary_intent="respiratory_distress",
            parsed_protocol_id="prot_respiratory_distress",
            reply="ok",
        ),
    ]
    inputs.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    summary = evaluate_generation_outputs(
        input_paths=[inputs],
        out_path=out,
        summary_path=summary_path,
    )

    breakdown = summary["safe_response_failure_breakdown"]
    assert breakdown["completed_cases"] == 2
    assert breakdown["safe_response_failed_cases"] == 2
    assert breakdown["blocking_metric_failure_counts"]["CorrectProtocolUse"] == 1
    assert breakdown["blocking_metric_failure_counts"]["HighRiskActionRecall"] == 1
    assert breakdown["blocking_metric_failure_counts"]["NegatedRiskAvoidance"] == 0
    assert summary_path.exists()


def _row(
    *,
    case_id: str,
    risk_level: str,
    expected_protocol_id: str,
    primary_intent: str,
    parsed_protocol_id: str,
    reply: str,
) -> dict[str, object]:
    return {
        "id": case_id,
        "system": "rair-rag",
        "status": "ok",
        "raw_input": "help",
        "case": {
            "id": case_id,
            "raw_input": "help",
            "canonical_input": "help",
            "expected_protocol_id": expected_protocol_id,
            "primary_intent": primary_intent,
            "risk_level": risk_level,
        },
        "parsed_output": {
            "protocol_id": parsed_protocol_id,
            "reply": reply,
            "safety_notes": [],
            "used_evidence": [],
            "_parse_ok": True,
        },
        "retrieved_evidence": [],
        "risk_context": {"primary_intent": primary_intent},
    }
