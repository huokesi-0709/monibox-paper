from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_INTENT_WEIGHTS = {
    "respiratory_distress": 1.00,
    "severe_bleeding_or_shock": 0.95,
    "crush_injury": 0.92,
    "altered_consciousness_or_head_injury": 0.90,
    "trapped_or_entrapment": 0.88,
    "aftershock_or_collapse_hazard": 0.84,
    "hypothermia": 0.82,
    "trauma_or_fracture": 0.78,
    "dehydration_or_resource_deprivation": 0.55,
    "psychological_distress": 0.45,
    "low_battery": 0.20,
    "out_of_scope": 0.05,
}

HIGH_RISK_INTENTS = {
    "respiratory_distress",
    "severe_bleeding_or_shock",
    "crush_injury",
    "altered_consciousness_or_head_injury",
    "trapped_or_entrapment",
    "aftershock_or_collapse_hazard",
    "hypothermia",
}

OPERATIONAL_CONSTRAINTS = {"low_battery"}


@dataclass(frozen=True)
class MultiIntentConfig:
    intent_base_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_INTENT_WEIGHTS)
    )
    confidence_threshold: float = 0.25
    high_risk_boost: float = 0.05
    operational_constraint_weight: float = 0.20


@dataclass(frozen=True)
class MultiIntentResult:
    primary_intent: str
    secondary_intents: list[str]
    operational_constraints: list[str]
    risk_score: float
    priority_trace: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultiIntentRouter:
    def __init__(self, config: MultiIntentConfig | None = None) -> None:
        self.config = config or MultiIntentConfig()

    def route(self, candidates: list[dict[str, Any]]) -> MultiIntentResult:
        scored = [
            self._score_candidate(candidate)
            for candidate in candidates
            if candidate_confidence(candidate)
            >= self.config.confidence_threshold
        ]
        scored.sort(
            key=lambda item: (
                item["is_operational"],
                -float(item["score"]),
                item["rank"],
                item["intent"],
            )
        )

        operational_constraints: list[str] = []
        risk_candidates: list[dict[str, Any]] = []
        for item in scored:
            intent = str(item["intent"])
            if item["is_operational"]:
                append_unique(operational_constraints, intent)
            else:
                risk_candidates.append(item)

        if risk_candidates:
            primary = str(risk_candidates[0]["intent"])
            secondary = [
                str(item["intent"])
                for item in risk_candidates[1:]
                if item["intent"] != primary
            ]
            risk_score = float(risk_candidates[0]["score"])
        elif operational_constraints:
            primary = operational_constraints[0]
            secondary = []
            risk_score = self.config.operational_constraint_weight
        else:
            primary = "out_of_scope"
            secondary = []
            risk_score = self.config.intent_base_weights.get("out_of_scope", 0.05)

        return MultiIntentResult(
            primary_intent=primary,
            secondary_intents=dedupe(secondary),
            operational_constraints=operational_constraints,
            risk_score=round(min(1.0, risk_score), 4),
            priority_trace=scored,
        )

    def _score_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        intent = str(candidate.get("risk") or candidate.get("intent") or "")
        original_confidence = float(candidate.get("confidence") or 0.0)
        adjusted_confidence = candidate_confidence(candidate)
        base_weight = self.config.intent_base_weights.get(intent, 0.1)
        is_operational = intent in OPERATIONAL_CONSTRAINTS
        if is_operational:
            score = min(base_weight, self.config.operational_constraint_weight)
        else:
            score = base_weight * (0.5 + adjusted_confidence * 0.5)
            if intent in HIGH_RISK_INTENTS:
                score += self.config.high_risk_boost
        return {
            "intent": intent,
            "term": candidate.get("term", candidate.get("trigger", "")),
            "trigger": candidate.get("trigger", candidate.get("term", "")),
            "confidence": original_confidence,
            "adjusted_confidence": adjusted_confidence,
            "effective_confidence": adjusted_confidence,
            "base_weight": base_weight,
            "evidence_type": candidate.get("evidence_type", ""),
            "score": round(score, 4),
            "is_operational": is_operational,
            "rank": self._rank(intent),
        }

    def _rank(self, intent: str) -> int:
        weights = self.config.intent_base_weights
        ordered = sorted(weights, key=lambda key: (-weights[key], key))
        try:
            return ordered.index(intent)
        except ValueError:
            return len(ordered)


def append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def dedupe(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        append_unique(output, item)
    return output


def candidate_confidence(candidate: dict[str, Any]) -> float:
    adjusted = candidate.get("adjusted_confidence")
    if adjusted is not None:
        return float(adjusted or 0.0)
    return float(candidate.get("confidence") or 0.0)
