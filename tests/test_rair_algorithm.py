from __future__ import annotations

from runtime.risk_router import RiskAwareInputRouter


def test_risk_candidates_include_algorithm_trace() -> None:
    ctx = RiskAwareInputRouter().route("我喘不上气，手机快没电了")

    assert ctx.risk_candidates
    candidate = next(
        item for item in ctx.risk_candidates if item["risk"] == "respiratory_distress"
    )
    assert candidate["risk"] == "respiratory_distress"
    assert candidate["trigger"]
    assert candidate["span"] == [candidate["start"], candidate["end"]]
    assert "confidence" in candidate
    assert "adjusted_confidence" in candidate
    assert "evidence_type" in candidate
    assert "confidence_components" in candidate
    assert {"f_lex", "f_sem", "f_ctx", "f_evi"} <= set(candidate["confidence_components"])


def test_risk_context_contains_complete_trace() -> None:
    ctx = RiskAwareInputRouter().route("我一直流血，现在特别害怕")
    payload = ctx.to_dict()

    assert payload["risk_candidates"]
    assert payload["positive_risks"]
    assert payload["negated_risks"] == []
    assert payload["primary_intent"] == "severe_bleeding_or_shock"
    assert "psychological_distress" in payload["secondary_intents"]
    assert payload["operational_constraints"] == []
    assert payload["suppressed_protocols"] == []
    assert payload["predicted_route"] == "route_bleeding_control"
    assert payload["protocol_id"] == "prot_bleeding_control"
    assert payload["risk_score"] > 0
    assert "trace" in payload
    assert "risk_context" in payload["trace"]
    assert payload["trace"]["risk_context"]["risk_candidates"]
