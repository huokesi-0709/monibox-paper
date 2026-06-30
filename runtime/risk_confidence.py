from __future__ import annotations

from math import exp
from typing import Any


def compute_candidate_confidence(candidate: Any, canonical_input: str, prototypes: Any) -> float:
    return archived_keyword_confidence(_candidate_trigger(candidate))


def compute_lexical_feature(candidate: Any) -> float:
    trigger = str(getattr(candidate, "trigger", "") or candidate.get("trigger", ""))
    return 1.0 if trigger else 0.0


def compute_semantic_feature(candidate: Any, prototypes: Any) -> float:
    return 0.5


def compute_context_feature(candidate: Any, text: str) -> float:
    return 0.5 if text else 0.0


def compute_evidence_feature(candidate: Any) -> float:
    return 1.0 if candidate else 0.0


def archived_keyword_confidence(term: str) -> float:
    return round(min(0.95, 0.55 + len(term) * 0.04), 4)


def confidence_for_term(term: str) -> float:
    """Retained for backward compatibility and archived keyword baseline only."""
    return archived_keyword_confidence(term)


def confidence_for_candidate(
    *,
    risk: str,
    legacy_intent: str,
    trigger: str,
    evidence_type: str,
    text: str = "",
) -> tuple[float, dict[str, float]]:
    components = confidence_components_for_candidate(
        risk=risk,
        legacy_intent=legacy_intent,
        trigger=trigger,
        evidence_type=evidence_type,
        text=text,
    )
    score = sigmoid(
        -0.8
        + 1.15 * components["f_lex"]
        + 1.00 * components["f_sem"]
        + 0.75 * components["f_ctx"]
        + 0.65 * components["f_evi"]
    )
    return round(score, 4), components


def confidence_components_for_candidate(
    *,
    risk: str,
    legacy_intent: str,
    trigger: str,
    evidence_type: str,
    text: str = "",
) -> dict[str, float]:
    normalized_risk = str(risk or "")
    normalized_legacy = str(legacy_intent or "")
    normalized_trigger = str(trigger or "")
    normalized_evidence = str(evidence_type or "unknown")
    normalized_text = str(text or "")
    f_lex = 1.0 if normalized_trigger else 0.0
    f_sem = semantic_prior_for_evidence(
        normalized_risk, normalized_legacy, normalized_evidence
    )
    f_ctx = contextual_signal(normalized_trigger, normalized_text)
    f_evi = evidence_signal(normalized_evidence)
    return {
        "f_lex": round(f_lex, 4),
        "f_sem": round(f_sem, 4),
        "f_ctx": round(f_ctx, 4),
        "f_evi": round(f_evi, 4),
    }


def _candidate_trigger(candidate: Any) -> str:
    if hasattr(candidate, "trigger"):
        return str(getattr(candidate, "trigger") or "")
    if isinstance(candidate, dict):
        return str(candidate.get("trigger") or candidate.get("term") or "")
    return str(candidate or "")


def semantic_prior_for_evidence(risk: str, legacy_intent: str, evidence_type: str) -> float:
    if risk == "low_battery" or legacy_intent == "low_battery":
        return 0.68
    if evidence_type == "protocol_alias":
        return 0.92
    if evidence_type == "scene_context":
        return 0.76
    if evidence_type == "operational":
        return 0.72
    if evidence_type == "lexical":
        return 0.62
    return 0.5


def contextual_signal(trigger: str, text: str) -> float:
    if not trigger:
        return 0.0
    if text and trigger in text:
        return 1.0
    return 0.55


def evidence_signal(evidence_type: str) -> float:
    if evidence_type == "protocol_alias":
        return 1.0
    if evidence_type == "scene_context":
        return 0.85
    if evidence_type == "operational":
        return 0.75
    if evidence_type == "lexical":
        return 0.65
    return 0.5


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))
