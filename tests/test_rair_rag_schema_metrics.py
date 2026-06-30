from __future__ import annotations

import pytest

from benchmarks.rair_rag.routing_metrics import compute_routing_metrics
from benchmarks.rair_rag.routing_schema import RoutingCase


def test_routing_case_validates_required_fields() -> None:
    case = RoutingCase.from_dict(
        {
            "id": "neg_0001",
            "canonical_id": "case_bleeding_neg_0001",
            "raw_input": "我腿疼但是没流血",
            "canonical_input": "我腿疼，但是没有流血",
            "language": "zh-CN",
            "source_type": "template_generated_human_reviewed",
            "guideline_refs": [{"source_id": "WHO_BEC_2018"}],
            "perturbation_types": ["negation_conflict"],
            "risk_mentions": ["pain", "bleeding"],
            "positive_risks": ["trauma_or_fracture"],
            "negated_risks": ["severe_bleeding_or_shock"],
            "primary_intent": "trauma_or_fracture",
            "expected_route": "route_trauma_or_fracture",
            "should_not_trigger": ["prot_bleeding_control"],
            "risk_level": "medium",
        }
    )

    assert case.primary_intent == "trauma_or_fracture"
    assert case.to_dict()["negated_risks"] == ["severe_bleeding_or_shock"]
    assert case.suppressed_protocols == ["prot_bleeding_control"]


def test_routing_case_supports_risk_context_annotations() -> None:
    case = RoutingCase.from_dict(
        {
            "id": "neg_0002",
            "canonical_id": "case_bleeding_neg_0002",
            "raw_input": "我腿疼但是没流血",
            "canonical_input": "我腿疼，但是没有流血",
            "language": "zh-CN",
            "source_type": "template_generated_human_reviewed",
            "perturbation_types": ["negation_conflict"],
            "risk_mentions": ["pain", "bleeding"],
            "risk_candidates": [
                {
                    "risk": "severe_bleeding_or_shock",
                    "trigger": "流血",
                    "span": [8, 10],
                    "confidence": 0.71,
                    "evidence_type": "lexical",
                    "negated": True,
                    "adjusted_confidence": 0.3905,
                }
            ],
            "positive_risks": ["trauma_or_fracture"],
            "negated_risks": ["severe_bleeding_or_shock"],
            "primary_intent": "trauma_or_fracture",
            "expected_route": "route_trauma_or_fracture",
            "should_not_trigger": ["prot_bleeding_control"],
            "suppressed_protocols": ["prot_bleeding_control"],
            "safety_boundaries": ["negation_conflict"],
            "risk_level": "medium",
        }
    )

    payload = case.to_dict()
    assert payload["risk_candidates"][0]["trigger"] == "流血"
    assert payload["suppressed_protocols"] == ["prot_bleeding_control"]
    assert payload["safety_boundaries"] == ["negation_conflict"]


def test_routing_case_rejects_bad_risk_candidates() -> None:
    with pytest.raises(ValueError, match="risk_candidates"):
        RoutingCase.from_dict(
            {
                "id": "x",
                "canonical_id": "x",
                "raw_input": "我疼",
                "canonical_input": "我疼",
                "primary_intent": "trauma_or_fracture",
                "risk_candidates": ["not-an-object"],
                "risk_level": "medium",
            }
        )


def test_routing_case_rejects_bad_risk_level() -> None:
    with pytest.raises(ValueError, match="risk_level"):
        RoutingCase.from_dict(
            {
                "id": "x",
                "canonical_id": "x",
                "raw_input": "我疼",
                "canonical_input": "我疼",
                "primary_intent": "trauma_or_fracture",
                "risk_level": "urgent",
            }
        )


def test_routing_metrics_detect_false_trigger_and_sets() -> None:
    cases = [
        RoutingCase.from_dict(
            {
                "id": "neg_0001",
                "canonical_id": "case_bleeding_neg_0001",
                "raw_input": "我腿疼但是没流血",
                "canonical_input": "我腿疼，但是没有流血",
                "language": "zh-CN",
                "source_type": "template_generated_human_reviewed",
                "perturbation_types": ["negation_conflict"],
                "positive_risks": ["trauma_or_fracture"],
                "negated_risks": ["severe_bleeding_or_shock"],
                "primary_intent": "trauma_or_fracture",
                "expected_route": "route_trauma_or_fracture",
                "should_not_trigger": ["prot_bleeding_control"],
                "risk_level": "medium",
            }
        ),
        RoutingCase.from_dict(
            {
                "id": "multi_0001",
                "canonical_id": "case_resp_battery_0001",
                "raw_input": "我喘不上气，手机快没电了",
                "canonical_input": "我喘不上气，手机快没电了",
                "language": "zh-CN",
                "source_type": "template_generated_human_reviewed",
                "perturbation_types": ["multi_intent"],
                "positive_risks": ["respiratory_distress"],
                "primary_intent": "respiratory_distress",
                "operational_constraints": ["low_battery"],
                "expected_route": "route_respiratory_distress",
                "risk_level": "critical",
            }
        ),
        RoutingCase.from_dict(
            {
                "id": "cand_0001",
                "canonical_id": "case_candidate_0001",
                "raw_input": "鎴戝枠涓嶄笂姘旓紝鎵嬫満蹇病鐢典簡",
                "canonical_input": "鎴戝枠涓嶄笂姘旓紝鎵嬫満蹇病鐢典簡",
                "language": "zh-CN",
                "source_type": "template_generated_human_reviewed",
                "perturbation_types": ["multi_intent"],
                "risk_candidates": [
                    {
                        "risk": "respiratory_distress",
                        "trigger": "鍠樹笉涓婃皵",
                        "span": [1, 5],
                        "confidence": 0.71,
                        "evidence_type": "protocol_alias",
                        "expected_negated": False,
                    },
                    {
                        "risk": "low_battery",
                        "trigger": "蹇病鐢典簡",
                        "span": [8, 13],
                        "confidence": 0.71,
                        "evidence_type": "operational",
                        "expected_negated": False,
                    },
                ],
                "positive_risks": ["respiratory_distress"],
                "primary_intent": "respiratory_distress",
                "operational_constraints": ["low_battery"],
                "expected_route": "route_respiratory_distress",
                "risk_level": "critical",
                "should_not_trigger": [],
                "suppressed_protocols": [],
            }
        ),
    ]
    predictions = [
        {
            "predicted_route": "route_bleeding_control",
            "protocol_id": "prot_bleeding_control",
            "primary_intent": "severe_bleeding_or_shock",
            "negated_risks": [],
        },
        {
            "predicted_route": "route_respiratory_distress",
            "primary_intent": "respiratory_distress",
            "operational_constraints": ["low_battery"],
        },
        {
            "predicted_route": "route_respiratory_distress",
            "primary_intent": "respiratory_distress",
            "risk_candidates": [
                {
                    "risk": "respiratory_distress",
                    "trigger": "鍠樹笉涓婃皵",
                    "evidence_type": "protocol_alias",
                },
                {
                    "risk": "low_battery",
                    "trigger": "蹇病鐢典簡",
                    "evidence_type": "operational",
                },
            ],
            "suppressed_protocols": [],
        },
    ]

    metrics = compute_routing_metrics(cases, predictions)

    assert metrics["RouteAcc"] == pytest.approx(2 / 3)
    assert metrics["HRR"] == pytest.approx(1.0)
    assert metrics["PFTR"] == pytest.approx(1 / 3)
    assert metrics["ConstraintF1"] == pytest.approx(2 / 3)
    assert metrics["RiskCandidateF1"] == pytest.approx(1.0)
    assert metrics["EvidenceTypeAcc"] == pytest.approx(1.0)
    assert metrics["SuppressedProtocolF1"] == pytest.approx(0.0)
    assert "negation_conflict" in metrics["by_perturbation_type"]
    assert metrics["by_perturbation_type"]["multi_intent"]["RiskCandidateF1"] == pytest.approx(1.0)


def test_routing_metrics_defaults_missing_candidate_fields() -> None:
    case = RoutingCase.from_dict(
        {
            "id": "x",
            "canonical_id": "x",
            "raw_input": "鎴戠柤",
            "canonical_input": "鎴戠柤",
            "language": "zh-CN",
            "source_type": "unit_test",
            "primary_intent": "trauma_or_fracture",
            "expected_route": "route_trauma_or_fracture",
            "risk_level": "medium",
        }
    )
    metrics = compute_routing_metrics([case], [{"primary_intent": "trauma_or_fracture"}])

    assert metrics["RiskCandidateF1"] == 0.0
    assert metrics["EvidenceTypeAcc"] == 0.0
    assert metrics["SuppressedProtocolF1"] == 0.0
