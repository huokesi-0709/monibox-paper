from __future__ import annotations

import json
from pathlib import Path

from runtime.multi_intent_router import MultiIntentConfig, MultiIntentRouter
from runtime.risk_candidate import RiskCandidate
from runtime.risk_router import RiskAwareInputRouter
from runtime.routing_policy import RoutingPolicy


def test_negated_bleeding_is_suppressed_but_injury_stays_positive() -> None:
    ctx = RiskAwareInputRouter().route("\u6211\u817f\u75bc\uff0c\u4f46\u662f\u6ca1\u6d41\u8840")

    assert ctx.primary_intent == "trauma_or_fracture"
    assert "trauma_or_fracture" in ctx.positive_risks
    assert "severe_bleeding_or_shock" in ctx.negated_risks
    assert "severe_bleeding_or_shock" not in ctx.secondary_intents
    assert any(
        item["risk"] == "severe_bleeding_or_shock" and item["negated"]
        for item in ctx.risk_mentions
    )
    bleeding = next(
        item
        for item in ctx.risk_mentions
        if item["risk"] == "severe_bleeding_or_shock"
    )
    assert bleeding["negation_reason"] == "negation_word_in_left_window"
    assert bleeding["left_window"] == "\u6ca1"
    assert bleeding["right_window"] == ""

    trauma = next(
        item for item in ctx.risk_mentions if item["risk"] == "trauma_or_fracture"
    )
    assert trauma["negated"] is False
    assert trauma["negation_reason"] == ""
    assert trauma["boundary_blocked"] is True


def test_multi_intent_keeps_low_battery_as_operational_constraint() -> None:
    ctx = RiskAwareInputRouter().route(
        "\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u624b\u673a\u5feb\u6ca1\u7535\u4e86"
    )

    assert ctx.primary_intent == "respiratory_distress"
    assert "low_battery" in ctx.operational_constraints
    assert "low_battery" not in ctx.secondary_intents
    assert ctx.risk_score > 0.8
    trace = ctx.trace["priority_trace"]
    respiratory = next(
        item for item in trace if item["intent"] == "respiratory_distress"
    )
    assert respiratory["evidence_type"] == "protocol_alias"
    assert respiratory["adjusted_confidence"] == respiratory["confidence"]

    low_battery = next(item for item in trace if item["intent"] == "low_battery")
    assert low_battery["is_operational"] is True
    assert low_battery["evidence_type"] == "operational"


def test_low_battery_can_be_primary_when_it_is_the_only_signal() -> None:
    ctx = RiskAwareInputRouter().route("\u624b\u673a\u5feb\u6ca1\u7535\u4e86")

    assert ctx.primary_intent == "low_battery"
    assert ctx.operational_constraints == ["low_battery"]
    assert ctx.positive_risks == ["low_battery"]
    assert ctx.risk_mentions[0]["negated"] is False
    assert ctx.risk_mentions[0]["negation_reason"] == ""
    assert (
        ctx.risk_mentions[0]["adjusted_confidence"]
        == ctx.risk_mentions[0]["confidence"]
    )


def test_risk_mentions_include_structured_candidate_fields() -> None:
    mentions = RiskAwareInputRouter().extract_risk_mentions(
        "\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u624b\u673a\u5feb\u6ca1\u7535\u4e86\uff0c\u95e8\u6253\u4e0d\u5f00"
    )

    respiratory = next(
        item for item in mentions if item["risk"] == "respiratory_distress"
    )
    assert respiratory["trigger"] == "\u5598\u4e0d\u4e0a\u6c14"
    assert respiratory["term"] == respiratory["trigger"]
    assert respiratory["span"] == [respiratory["start"], respiratory["end"]]
    assert respiratory["evidence_type"] == "protocol_alias"
    assert respiratory["negated"] is False
    assert respiratory["adjusted_confidence"] == respiratory["confidence"]

    low_battery = next(item for item in mentions if item["risk"] == "low_battery")
    assert low_battery["evidence_type"] == "operational"

    trapped = next(
        item for item in mentions if item["risk"] == "trapped_or_entrapment"
    )
    assert trapped["trigger"] == "\u95e8\u6253\u4e0d\u5f00"
    assert trapped["evidence_type"] == "scene_context"


def test_extract_risk_candidates_returns_structured_objects() -> None:
    candidates = RiskAwareInputRouter().extract_risk_candidates(
        "\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u6211\u5598\u4e0d\u4e0a\u6c14"
    )

    assert candidates
    assert all(isinstance(candidate, RiskCandidate) for candidate in candidates)
    first = candidates[0]
    assert first.risk == "respiratory_distress"
    assert first.trigger == "\u5598\u4e0d\u4e0a\u6c14"
    assert first.span == [first.start, first.end]
    assert first.to_dict()["term"] == first.trigger


def test_negated_candidate_keeps_original_and_adjusted_confidence() -> None:
    ctx = RiskAwareInputRouter().route("\u6211\u817f\u75bc\uff0c\u4f46\u662f\u6ca1\u6d41\u8840")
    bleeding = next(
        item
        for item in ctx.risk_mentions
        if item["risk"] == "severe_bleeding_or_shock"
    )

    assert bleeding["negated"] is True
    assert bleeding["confidence"] > bleeding["adjusted_confidence"]
    assert bleeding["trigger"] == "\u6d41\u8840"
    assert bleeding["evidence_type"] == "lexical"


def test_zero_negation_penalty_prevents_negated_risk_suppression() -> None:
    ctx = RiskAwareInputRouter(RoutingPolicy(negation_penalty=0.0)).route(
        "\u6211\u817f\u75bc\uff0c\u4f46\u662f\u6ca1\u6d41\u8840"
    )
    bleeding = next(
        item
        for item in ctx.risk_mentions
        if item["risk"] == "severe_bleeding_or_shock"
    )

    assert bleeding["negated"] is False
    assert bleeding["negation_probability"] == 0.0
    assert bleeding["p_neg"] == 0.0
    assert bleeding["adjusted_confidence"] == bleeding["confidence"]
    assert "severe_bleeding_or_shock" not in ctx.negated_risks
    assert "prot_bleeding_control" not in ctx.suppressed_protocols


def test_extreme_negation_penalty_bounds_confidence_and_keeps_suppression() -> None:
    ctx = RiskAwareInputRouter(RoutingPolicy(negation_penalty=10.0)).route(
        "\u6211\u817f\u75bc\uff0c\u4f46\u662f\u6ca1\u6d41\u8840"
    )
    bleeding = next(
        item
        for item in ctx.risk_mentions
        if item["risk"] == "severe_bleeding_or_shock"
    )

    assert bleeding["negated"] is True
    assert bleeding["negation_probability"] == 1.0
    assert bleeding["p_neg"] == 1.0
    assert bleeding["adjusted_confidence"] == 0.0
    assert "severe_bleeding_or_shock" in ctx.negated_risks
    assert "prot_bleeding_control" in ctx.suppressed_protocols


def test_routing_context_builds_pre_retrieval_risk_context() -> None:
    ctx = RiskAwareInputRouter().route("\u6211\u817f\u75bc\uff0c\u4f46\u662f\u6ca1\u6d41\u8840")
    retrieval_context = ctx.to_retrieval_context()

    assert ctx.predicted_route == "route_trauma_or_fracture"
    assert ctx.protocol_id == "prot_injury_fracture"
    assert ctx.suppressed_protocols == ["prot_bleeding_control"]
    assert ctx.risk_candidates == ctx.risk_mentions
    assert retrieval_context == {
        "primary_intent": "trauma_or_fracture",
        "secondary_intents": [],
        "positive_risks": ["trauma_or_fracture"],
        "negated_risks": ["severe_bleeding_or_shock"],
        "operational_constraints": [],
        "suppressed_protocols": ["prot_bleeding_control"],
        "predicted_route": "route_trauma_or_fracture",
        "protocol_id": "prot_injury_fracture",
        "risk_score": ctx.risk_score,
    }


def test_right_window_negation_only_suppresses_the_following_risk() -> None:
    ctx = RiskAwareInputRouter().route(
        "\u6211\u4e00\u76f4\u6d41\u8840\uff0c\u6ca1\u6709\u5598\u4e0d\u4e0a\u6c14"
    )

    bleeding = next(
        item
        for item in ctx.risk_mentions
        if item["risk"] == "severe_bleeding_or_shock"
    )
    respiratory = next(
        item for item in ctx.risk_mentions if item["risk"] == "respiratory_distress"
    )

    assert bleeding["negated"] is False
    assert bleeding["negation_reason"] == ""
    assert bleeding["boundary_blocked"] is True
    assert respiratory["negated"] is True
    assert respiratory["negation_reason"] == "negation_word_in_left_window"
    assert respiratory["left_window"] == "\u6ca1\u6709"
    assert respiratory["adjusted_confidence"] < respiratory["confidence"]


def test_multi_intent_uses_adjusted_confidence_for_threshold_and_trace() -> None:
    result = MultiIntentRouter(
        MultiIntentConfig(confidence_threshold=0.5)
    ).route(
        [
            {
                "risk": "respiratory_distress",
                "trigger": "\u5598\u4e0d\u4e0a\u6c14",
                "confidence": 0.9,
                "adjusted_confidence": 0.2,
                "evidence_type": "protocol_alias",
            },
            {
                "risk": "severe_bleeding_or_shock",
                "trigger": "\u4e00\u76f4\u6d41\u8840",
                "confidence": 0.7,
                "adjusted_confidence": 0.7,
                "evidence_type": "protocol_alias",
            },
        ]
    )

    assert result.primary_intent == "severe_bleeding_or_shock"
    assert all(
        item["intent"] != "respiratory_distress"
        for item in result.priority_trace
    )
    bleeding = result.priority_trace[0]
    assert bleeding["confidence"] == 0.7
    assert bleeding["adjusted_confidence"] == 0.7
    assert bleeding["effective_confidence"] == 0.7
    assert bleeding["evidence_type"] == "protocol_alias"
    assert "score" in bleeding
    assert "base_weight" in bleeding


def test_multi_intent_prioritizes_bleeding_and_keeps_operational_constraint() -> None:
    ctx = RiskAwareInputRouter().route(
        "\u6211\u88ab\u56f0\u4f4f\u4e86\uff0c\u817f\u4e0a\u4e00\u76f4\u6d41\u8840\uff0c\u624b\u673a\u5feb\u6ca1\u7535\u4e86"
    )

    assert ctx.primary_intent == "severe_bleeding_or_shock"
    assert "trapped_or_entrapment" in ctx.secondary_intents
    assert "low_battery" in ctx.operational_constraints
    assert "low_battery" not in ctx.secondary_intents


def test_policy_can_load_from_json_and_yaml(tmp_path: Path) -> None:
    json_policy = tmp_path / "policy.json"
    json_policy.write_text(
        json.dumps(
            {
                "negation_window": 8,
                "confidence_threshold": 0.1,
                "high_risk_boost": 0.07,
                "intent_base_weights": {"psychological_distress": 0.99},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded_json = RoutingPolicy.from_file(json_policy)
    assert loaded_json.negation_window == 8
    assert loaded_json.high_risk_boost == 0.07
    assert loaded_json.intent_base_weights["psychological_distress"] == 0.99
    assert RoutingPolicy.from_dict({"negation_penalty": 0.0}).negation_penalty == 0.0

    yaml_policy = tmp_path / "policy.yaml"
    yaml_policy.write_text(
        "\n".join(
            [
                "negation_window: 5",
                "confidence_threshold: 0.2",
                "intent_base_weights:",
                "  respiratory_distress: 1.0",
                "  low_battery: 0.1",
            ]
        ),
        encoding="utf-8",
    )
    loaded_yaml = RoutingPolicy.from_file(yaml_policy)
    assert loaded_yaml.negation_window == 5
    assert loaded_yaml.confidence_threshold == 0.2
    assert loaded_yaml.intent_base_weights["low_battery"] == 0.1


def test_policy_weight_can_change_priority() -> None:
    policy = RoutingPolicy.from_dict(
        {
            "intent_base_weights": {
                "psychological_distress": 1.2,
                "respiratory_distress": 0.4,
            }
        }
    )
    ctx = RiskAwareInputRouter(policy).route(
        "\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u4e5f\u5f88\u5bb3\u6015"
    )

    assert ctx.primary_intent == "psychological_distress"
    assert "respiratory_distress" in ctx.secondary_intents
