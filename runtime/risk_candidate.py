from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from runtime.risk_confidence import confidence_components_for_candidate, confidence_for_candidate

EvidenceType = Literal[
    "lexical",
    "protocol_alias",
    "operational",
    "scene_context",
    "unknown",
]

LEXICAL: EvidenceType = "lexical"
PROTOCOL_ALIAS: EvidenceType = "protocol_alias"
OPERATIONAL: EvidenceType = "operational"
SCENE_CONTEXT: EvidenceType = "scene_context"
UNKNOWN: EvidenceType = "unknown"

PROTOCOL_ALIAS_TRIGGERS = {
    "血止不住",
    "一直流血",
    "血一直",
    "血没有停",
    "喷血",
    "冒血",
    "往外冒",
    "喘不上气",
    "喘不过气",
    "呼吸困难",
    "呼吸很费力",
    "吸不上气",
    "窒息",
}

SCENE_CONTEXT_TRIGGERS = {
    "废墟",
    "门打不开",
    "打不开",
    "余震",
    "地震",
    "坍塌",
    "倒塌",
    "被困",
    "困住",
    "出不去",
    "出不来",
    "出不来了",
    "瓦砾",
}

PROTOCOL_ALIAS_RISKS = {"severe_bleeding_or_shock", "respiratory_distress"}
SCENE_CONTEXT_RISKS = {"trapped_or_entrapment", "aftershock_or_collapse_hazard"}


@dataclass(frozen=True)
class RiskCandidate:
    risk: str
    legacy_intent: str
    trigger: str
    start: int
    end: int
    confidence: float
    evidence_type: EvidenceType
    negated: bool = False
    adjusted_confidence: float | None = None
    confidence_components: dict[str, float] | None = None

    @property
    def span(self) -> list[int]:
        return [self.start, self.end]

    def to_dict(self) -> dict[str, object]:
        adjusted = (
            self.confidence
            if self.adjusted_confidence is None
            else self.adjusted_confidence
        )
        return {
            "risk": self.risk,
            "legacy_intent": self.legacy_intent,
            "trigger": self.trigger,
            "term": self.trigger,
            "start": self.start,
            "end": self.end,
            "span": self.span,
            "confidence": self.confidence,
            "evidence_type": self.evidence_type,
            "negated": self.negated,
            "adjusted_confidence": adjusted,
            "confidence_components": dict(self.confidence_components or {}),
        }


def candidate_to_dict(candidate: RiskCandidate) -> dict[str, object]:
    return candidate.to_dict()


def infer_evidence_type(risk: str, legacy_intent: str, trigger: str) -> EvidenceType:
    normalized_risk = str(risk or "")
    normalized_legacy = str(legacy_intent or "")
    normalized_trigger = str(trigger or "")
    if not normalized_risk or not normalized_trigger:
        return UNKNOWN
    if normalized_risk == "low_battery" or normalized_legacy == "low_battery":
        return OPERATIONAL
    if normalized_risk in SCENE_CONTEXT_RISKS and contains_any(
        normalized_trigger, SCENE_CONTEXT_TRIGGERS
    ):
        return SCENE_CONTEXT
    if normalized_risk in PROTOCOL_ALIAS_RISKS and contains_any(
        normalized_trigger, PROTOCOL_ALIAS_TRIGGERS
    ):
        return PROTOCOL_ALIAS
    return LEXICAL


def build_candidate_confidence(
    *,
    risk: str,
    legacy_intent: str,
    trigger: str,
    evidence_type: str,
    text: str = "",
) -> tuple[float, dict[str, float]]:
    score, components = confidence_for_candidate(
        risk=risk,
        legacy_intent=legacy_intent,
        trigger=trigger,
        evidence_type=evidence_type,
        text=text,
    )
    return score, components


def contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)
