from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.rair_rag.routing_schema import RoutingCase, load_routing_cases
from benchmarks.rair_rag.scripts.generate_candidates import (
    build_risk_candidates,
    expand_template,
    expand_template_with_slots,
    generate_candidates,
    write_jsonl,
)

EVIDENCE_TYPES = {
    "lexical",
    "protocol_alias",
    "operational",
    "scene_context",
    "unknown",
}


def test_generate_candidates_from_templates(tmp_path: Path) -> None:
    candidates = generate_candidates(Path("benchmarks/rair_rag/templates"))

    assert len(candidates) == 817
    assert {candidate["id"].split("_")[0] for candidate in candidates} == {
        "boundary",
        "clean",
        "multi",
        "neg",
    }
    assert all(candidate["needs_human_review"] is True for candidate in candidates)
    assert all(
        candidate["source_type"] == "template_generated" for candidate in candidates
    )
    assert all(candidate["risk_candidates"] for candidate in candidates)
    for candidate in candidates:
        assert candidate["suppressed_protocols"] == candidate["should_not_trigger"]
        for risk_candidate in candidate["risk_candidates"]:
            assert isinstance(risk_candidate["risk"], str)
            assert isinstance(risk_candidate["trigger"], str)
            assert isinstance(risk_candidate["confidence"], float)
            assert risk_candidate["evidence_type"] in EVIDENCE_TYPES
            assert isinstance(risk_candidate["expected_negated"], bool)
            assert isinstance(risk_candidate["span"], list)
            assert len(risk_candidate["span"]) == 2
        RoutingCase.from_dict(candidate)

    operational_only = [
        candidate
        for candidate in candidates
        if candidate["template_id"] == "clean_low_battery_001"
    ]
    assert operational_only
    assert all(candidate["expected_route"] is None for candidate in operational_only)
    assert all(
        candidate["operational_constraints"] == ["low_battery"]
        for candidate in operational_only
    )

    negation_case = next(
        candidate
        for candidate in candidates
        if candidate["template_id"] == "neg_bleeding_pain_001"
    )
    assert any(
        risk_candidate["risk"] == "severe_bleeding_or_shock"
        and risk_candidate["expected_negated"] is True
        for risk_candidate in negation_case["risk_candidates"]
    )
    assert any(
        risk_candidate["risk"] == "trauma_or_fracture"
        and risk_candidate["expected_negated"] is False
        for risk_candidate in negation_case["risk_candidates"]
    )

    multi_intent_case = next(
        candidate
        for candidate in candidates
        if candidate["template_id"] == "multi_resp_battery_001"
    )
    assert any(
        risk_candidate["risk"] == "respiratory_distress"
        and risk_candidate["evidence_type"] == "protocol_alias"
        for risk_candidate in multi_intent_case["risk_candidates"]
    )
    assert any(
        risk_candidate["risk"] == "low_battery"
        and risk_candidate["evidence_type"] == "operational"
        for risk_candidate in multi_intent_case["risk_candidates"]
    )

    fixed_trigger_case = next(
        candidate
        for candidate in candidates
        if candidate["template_id"] == "clean_crush_002"
    )
    assert any(
        risk_candidate["risk"] == "crush_injury"
        and risk_candidate["trigger"] == "重物压着"
        for risk_candidate in fixed_trigger_case["risk_candidates"]
    )

    out = tmp_path / "rair_candidates.jsonl"
    write_jsonl(candidates, out)
    loaded_cases = load_routing_cases(out)
    assert len(loaded_cases) == len(candidates)
    assert all(case.risk_candidates for case in loaded_cases)


def test_expand_template_with_slots_preserves_legacy_expand_template() -> None:
    template = {
        "template_id": "example",
        "pattern": "我{body_part}疼，但是没{bleeding_term}",
        "slots": {
            "body_part": ["腿"],
            "bleeding_term": ["流血"],
        },
    }

    expanded = expand_template_with_slots(template)

    assert expanded == [
        {
            "raw_input": "我腿疼，但是没流血",
            "slot_values": {
                "body_part": "腿",
                "bleeding_term": "流血",
            },
        }
    ]
    assert expand_template(template) == ["我腿疼，但是没流血"]


def test_build_risk_candidates_raises_for_missing_trigger() -> None:
    template = {
        "template_id": "bad_trigger",
        "candidate_annotations": [
            {
                "trigger": "不存在",
                "risk": "trauma_or_fracture",
                "evidence_type": "lexical",
                "expected_negated": False,
            }
        ],
    }

    with pytest.raises(ValueError, match="bad_trigger.*not found"):
        build_risk_candidates(template, "我腿疼", {})
