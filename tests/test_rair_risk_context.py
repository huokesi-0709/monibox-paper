from __future__ import annotations

from runtime.risk_router import RiskAwareInputRouter


def test_risk_context_has_complete_fields() -> None:
    ctx = RiskAwareInputRouter().route("我手机快没电了，而且喘不上气")
    payload = ctx.to_dict()

    assert payload["risk_candidates"]
    assert payload["positive_risks"]
    assert payload["negated_risks"] == []
    assert payload["primary_intent"] == "respiratory_distress"
    assert "low_battery" in payload["operational_constraints"]
    assert payload["suppressed_protocols"] == []
    assert payload["predicted_route"] == "route_respiratory_distress"
    assert payload["protocol_id"] == "prot_respiratory_distress"
    assert payload["risk_score"] > 0
    assert "trace" in payload


def test_out_of_scope_input_stays_out_of_scope() -> None:
    ctx = RiskAwareInputRouter().route("你能帮我写诗吗")

    assert ctx.primary_intent == "out_of_scope"
    assert ctx.predicted_route == "route_out_of_scope" or ctx.predicted_route is None
    assert "prot_bleeding_control" not in ctx.suppressed_protocols
