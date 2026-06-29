from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from runtime.intent_extractor import INTENT_TERMS
from runtime.multi_intent_router import MultiIntentConfig, MultiIntentRouter
from runtime.negation_resolver import NegationConfig, NegationResolver
from runtime.routing_policy import RoutingPolicy

LEGACY_TO_RAIR_LABEL = {
    "respiratory_distress": "respiratory_distress",
    "severe_bleeding": "severe_bleeding_or_shock",
    "head_or_consciousness": "altered_consciousness_or_head_injury",
    "collapse_aftershock": "aftershock_or_collapse_hazard",
    "hypothermia": "hypothermia",
    "dehydration": "dehydration_or_resource_deprivation",
    "pain_or_injury": "trauma_or_fracture",
    "panic": "psychological_distress",
    "low_battery": "low_battery",
    "out_of_scope": "out_of_scope",
}

CRUSH_TERMS = (
    "压",
    "被压",
    "压住",
    "挤压",
    "重物",
    "埋住",
    "砸",
)


@dataclass(frozen=True)
class RiskRoutingContext:
    raw_text: str
    canonical_text: str
    risk_mentions: list[dict[str, Any]]
    positive_risks: list[str]
    negated_risks: list[str]
    primary_intent: str
    secondary_intents: list[str]
    operational_constraints: list[str]
    risk_score: float
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskAwareInputRouter:
    def __init__(self, policy: RoutingPolicy | None = None) -> None:
        self.policy = policy or RoutingPolicy()
        self.negation_resolver = NegationResolver(
            NegationConfig(
                negation_window=self.policy.negation_window,
                negation_words=self.policy.negation_words,
                boundary_terms=self.policy.boundary_terms,
                negation_penalty=self.policy.negation_penalty,
            )
        )
        self.multi_intent_router = MultiIntentRouter(
            MultiIntentConfig(
                intent_base_weights=self.policy.intent_base_weights,
                confidence_threshold=self.policy.confidence_threshold,
                high_risk_boost=self.policy.high_risk_boost,
                operational_constraint_weight=self.policy.operational_constraint_weight,
            )
        )

    def route(
        self, raw_text: str, canonical_text: str | None = None
    ) -> RiskRoutingContext:
        raw = "" if raw_text is None else str(raw_text)
        canonical = raw.strip() if canonical_text is None else str(canonical_text).strip()
        risk_mentions = self.extract_risk_mentions(canonical)
        negation = self.negation_resolver.resolve(canonical, risk_mentions)
        positive_mentions = [
            mention for mention in negation.mentions if not mention.get("negated")
        ]
        route_result = self.multi_intent_router.route(positive_mentions)

        return RiskRoutingContext(
            raw_text=raw,
            canonical_text=canonical,
            risk_mentions=negation.mentions,
            positive_risks=negation.positive_risks,
            negated_risks=negation.negated_risks,
            primary_intent=route_result.primary_intent,
            secondary_intents=route_result.secondary_intents,
            operational_constraints=route_result.operational_constraints,
            risk_score=route_result.risk_score,
            trace={
                "negation_trace": negation.negation_trace,
                "priority_trace": route_result.priority_trace,
                "policy": self.policy.to_dict(),
            },
        )

    def extract_risk_mentions(self, text: str) -> list[dict[str, Any]]:
        mentions: list[dict[str, Any]] = []
        for legacy_intent, terms in INTENT_TERMS.items():
            for term in terms:
                if not term:
                    continue
                for match in re.finditer(re.escape(term), text):
                    risk = map_legacy_intent(legacy_intent, term)
                    mentions.append(
                        {
                            "risk": risk,
                            "legacy_intent": legacy_intent,
                            "term": term,
                            "start": match.start(),
                            "end": match.end(),
                            "confidence": confidence_for_term(term),
                        }
                    )
        return sorted(
            dedupe_mentions(mentions),
            key=lambda item: (int(item["start"]), int(item["end"]), str(item["risk"])),
        )


def map_legacy_intent(legacy_intent: str, term: str) -> str:
    if legacy_intent == "trapped_or_crush":
        if any(item in term for item in CRUSH_TERMS):
            return "crush_injury"
        return "trapped_or_entrapment"
    return LEGACY_TO_RAIR_LABEL.get(legacy_intent, legacy_intent)


def confidence_for_term(term: str) -> float:
    return round(min(0.95, 0.55 + len(term) * 0.04), 4)


def dedupe_mentions(mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, int, int]] = set()
    output: list[dict[str, Any]] = []
    for mention in mentions:
        key = (
            str(mention.get("risk", "")),
            str(mention.get("term", "")),
            int(mention.get("start", 0)),
            int(mention.get("end", 0)),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(mention)
    return output
