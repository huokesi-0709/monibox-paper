from __future__ import annotations

from runtime.risk_candidate import build_candidate_confidence
from runtime.risk_router import RiskAwareInputRouter


def test_confidence_components_are_exposed() -> None:
    ctx = RiskAwareInputRouter().route("我喘不上气，手机快没电了")
    respiratory = next(
        item for item in ctx.risk_candidates if item["risk"] == "respiratory_distress"
    )

    components = respiratory["confidence_components"]
    assert components["f_lex"] > 0
    assert components["f_sem"] > 0
    assert components["f_ctx"] > 0
    assert components["f_evi"] > 0
    assert respiratory["confidence"] == respiratory["adjusted_confidence"]


def test_candidate_confidence_helper_returns_components() -> None:
    score, components = build_candidate_confidence(
        risk="respiratory_distress",
        legacy_intent="respiratory_distress",
        trigger="喘不上气",
        evidence_type="protocol_alias",
        text="我喘不上气",
    )

    assert 0 < score <= 1
    assert {"f_lex", "f_sem", "f_ctx", "f_evi"} <= set(components)
