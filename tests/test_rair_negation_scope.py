from __future__ import annotations

from runtime.risk_router import RiskAwareInputRouter


def test_negation_scope_trace_exposes_probability_terms() -> None:
    ctx = RiskAwareInputRouter().route("我腿疼，但是没流血")

    assert "severe_bleeding_or_shock" in ctx.negated_risks
    assert "prot_bleeding_control" in ctx.suppressed_protocols
    bleeding = next(
        item for item in ctx.risk_candidates if item["risk"] == "severe_bleeding_or_shock"
    )
    assert bleeding["negated"] is True
    assert bleeding["negation_probability"] >= 0
    assert bleeding["negation_strength"] >= 0
    assert bleeding["distance_decay"] >= 0
    assert bleeding["boundary_penalty"] >= 0
    assert bleeding["negation_reason"] == "negation_word_in_left_window"
    assert bleeding["adjusted_confidence"] < bleeding["confidence"]


def test_non_negatable_risks_are_preserved() -> None:
    ctx = RiskAwareInputRouter().route("手机快没电了")

    battery = next(item for item in ctx.risk_candidates if item["risk"] == "low_battery")
    assert battery["negated"] is False
    assert battery["adjusted_confidence"] == battery["confidence"]
