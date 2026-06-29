from __future__ import annotations

import json
from pathlib import Path

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


def test_multi_intent_keeps_low_battery_as_operational_constraint() -> None:
    ctx = RiskAwareInputRouter().route(
        "\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u624b\u673a\u5feb\u6ca1\u7535\u4e86"
    )

    assert ctx.primary_intent == "respiratory_distress"
    assert "low_battery" in ctx.operational_constraints
    assert "low_battery" not in ctx.secondary_intents
    assert ctx.risk_score > 0.8


def test_low_battery_can_be_primary_when_it_is_the_only_signal() -> None:
    ctx = RiskAwareInputRouter().route("\u624b\u673a\u5feb\u6ca1\u7535\u4e86")

    assert ctx.primary_intent == "low_battery"
    assert ctx.operational_constraints == ["low_battery"]
    assert ctx.positive_risks == ["low_battery"]


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
