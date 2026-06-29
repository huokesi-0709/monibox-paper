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
    ]

    metrics = compute_routing_metrics(cases, predictions)

    assert metrics["RouteAcc"] == 0.5
    assert metrics["HRR"] == 1.0
    assert metrics["PFTR"] == 0.5
    assert metrics["ConstraintF1"] == 1.0
    assert "negation_conflict" in metrics["by_perturbation_type"]

