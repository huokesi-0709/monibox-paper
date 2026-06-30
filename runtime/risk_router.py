from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from runtime.intent_extractor import INTENT_TERMS
from runtime.multi_intent_router import MultiIntentConfig, MultiIntentRouter
from runtime.negation_resolver import NegationConfig, NegationResolver
from runtime.risk_confidence import confidence_for_term
from runtime.risk_candidate import (
    RiskCandidate,
    build_candidate_confidence,
    infer_evidence_type,
)
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

ROUTE_BY_INTENT = {
    "respiratory_distress": "route_respiratory_distress",
    "severe_bleeding_or_shock": "route_bleeding_control",
    "trauma_or_fracture": "route_trauma_or_fracture",
    "crush_injury": "route_crush_injury",
    "altered_consciousness_or_head_injury": "route_head_or_consciousness",
    "hypothermia": "route_hypothermia",
    "psychological_distress": "route_psychological_support",
    "trapped_or_entrapment": "route_trapped_or_entrapment",
    "aftershock_or_collapse_hazard": "route_aftershock_or_collapse_hazard",
    "dehydration_or_resource_deprivation": "route_dehydration_or_resource_deprivation",
    "out_of_scope": "route_out_of_scope",
}

PROTOCOL_BY_ROUTE = {
    "route_respiratory_distress": "prot_respiratory_distress",
    "route_bleeding_control": "prot_bleeding_control",
    "route_trauma_or_fracture": "prot_injury_fracture",
    "route_crush_injury": "prot_crush_injury",
    "route_head_or_consciousness": "prot_head_injury",
    "route_hypothermia": "prot_hypothermia",
    "route_psychological_support": "prot_psychological_support",
    "route_trapped_or_entrapment": "prot_entrapment",
    "route_aftershock_or_collapse_hazard": "prot_aftershock_collapse",
    "route_dehydration_or_resource_deprivation": "prot_resource_deprivation",
    "route_out_of_scope": None,
}

CRUSH_TERMS = (
    "压",
    "被压",
    "压住",
    "挤压",
    "重物",
    "埋住",
    "砸",
    "胸膛被卡住",
    "胳膊被卡住",
)


@dataclass(frozen=True)
class RiskRoutingContext:
    raw_text: str
    canonical_text: str
    risk_candidates: list[dict[str, Any]]
    risk_mentions: list[dict[str, Any]]
    positive_risks: list[str]
    negated_risks: list[str]
    primary_intent: str
    secondary_intents: list[str]
    operational_constraints: list[str]
    suppressed_protocols: list[str]
    predicted_route: str | None
    protocol_id: str | None
    risk_score: float
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_retrieval_context(self) -> dict[str, Any]:
        return {
            "primary_intent": self.primary_intent,
            "secondary_intents": list(self.secondary_intents),
            "positive_risks": list(self.positive_risks),
            "negated_risks": list(self.negated_risks),
            "operational_constraints": list(self.operational_constraints),
            "suppressed_protocols": list(self.suppressed_protocols),
            "predicted_route": self.predicted_route,
            "protocol_id": self.protocol_id,
            "risk_score": self.risk_score,
        }


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
        risk_candidates = self.extract_risk_candidates(canonical)
        risk_mentions = [candidate.to_dict() for candidate in risk_candidates]
        negation = self.negation_resolver.resolve(canonical, risk_mentions)
        positive_mentions = [
            mention for mention in negation.mentions if not mention.get("negated")
        ]
        route_result = self.multi_intent_router.route(positive_mentions)
        predicted_route = route_for_intent(route_result.primary_intent)
        protocol_id = protocol_for_route(predicted_route)
        suppressed_protocols = suppressed_protocols_for_negated_risks(
            negation.negated_risks
        )

        return RiskRoutingContext(
            raw_text=raw,
            canonical_text=canonical,
            risk_candidates=negation.mentions,
            risk_mentions=negation.mentions,
            positive_risks=negation.positive_risks,
            negated_risks=negation.negated_risks,
            primary_intent=route_result.primary_intent,
            secondary_intents=route_result.secondary_intents,
            operational_constraints=route_result.operational_constraints,
            suppressed_protocols=suppressed_protocols,
            predicted_route=predicted_route,
            protocol_id=protocol_id,
            risk_score=route_result.risk_score,
            trace={
                "risk_candidates": negation.mentions,
                "negation_trace": negation.negation_trace,
                "priority_trace": route_result.priority_trace,
                "risk_context": {
                    "risk_candidates": negation.mentions,
                    "positive_risks": negation.positive_risks,
                    "negated_risks": negation.negated_risks,
                    "primary_intent": route_result.primary_intent,
                    "secondary_intents": route_result.secondary_intents,
                    "operational_constraints": route_result.operational_constraints,
                    "suppressed_protocols": suppressed_protocols,
                    "predicted_route": predicted_route,
                    "protocol_id": protocol_id,
                    "risk_score": route_result.risk_score,
                },
                "policy": self.policy.to_dict(),
                "retrieval_context": {
                    "predicted_route": predicted_route,
                    "protocol_id": protocol_id,
                    "suppressed_protocols": suppressed_protocols,
                },
            },
        )

    def extract_risk_candidates(self, text: str) -> list[RiskCandidate]:
        candidates: list[RiskCandidate] = []
        for legacy_intent, terms in INTENT_TERMS.items():
            for term in terms:
                if not term:
                    continue
                for match in re.finditer(re.escape(term), text):
                    risk = map_legacy_intent(legacy_intent, term)
                    evidence_type = infer_evidence_type(risk, legacy_intent, term)
                    confidence, components = build_candidate_confidence(
                        risk=risk,
                        legacy_intent=legacy_intent,
                        trigger=term,
                        evidence_type=evidence_type,
                        text=text,
                    )
                    candidate = RiskCandidate(
                        risk=risk,
                        legacy_intent=legacy_intent,
                        trigger=term,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        evidence_type=evidence_type,
                        confidence_components=components,
                    )
                    candidates.append(candidate)
        return sorted(
            dedupe_candidates(candidates),
            key=lambda item: (item.start, item.end, item.risk),
        )

    def extract_risk_mentions(self, text: str) -> list[dict[str, Any]]:
        return [
            candidate.to_dict()
            for candidate in self.extract_risk_candidates(text)
        ]


def map_legacy_intent(legacy_intent: str, term: str) -> str:
    if legacy_intent == "trapped_or_crush":
        if any(item in term for item in CRUSH_TERMS):
            return "crush_injury"
        return "trapped_or_entrapment"
    return LEGACY_TO_RAIR_LABEL.get(legacy_intent, legacy_intent)


def route_for_intent(intent: str) -> str | None:
    return ROUTE_BY_INTENT.get(intent)


def protocol_for_route(route: str | None) -> str | None:
    if not route:
        return None
    return PROTOCOL_BY_ROUTE.get(route)


def suppressed_protocols_for_negated_risks(negated_risks: list[str]) -> list[str]:
    protocols: list[str] = []
    for risk in negated_risks:
        protocol = protocol_for_route(route_for_intent(risk))
        if protocol and protocol not in protocols:
            protocols.append(protocol)
    return protocols


def dedupe_candidates(candidates: list[RiskCandidate]) -> list[RiskCandidate]:
    seen: set[tuple[str, str, int, int]] = set()
    output: list[RiskCandidate] = []
    for candidate in candidates:
        key = (candidate.risk, candidate.trigger, candidate.start, candidate.end)
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    return output
