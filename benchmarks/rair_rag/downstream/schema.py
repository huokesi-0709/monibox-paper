from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from benchmarks.rair_rag.routing_schema import RoutingCase


@dataclass
class DownstreamCase:
    id: str
    raw_input: str
    canonical_input: str
    expected_protocol_id: str | None = None
    expected_route: str = ""
    positive_risks: list[str] = field(default_factory=list)
    negated_risks: list[str] = field(default_factory=list)
    primary_intent: str = ""
    secondary_intents: list[str] = field(default_factory=list)
    operational_constraints: list[str] = field(default_factory=list)
    should_not_trigger: list[str] = field(default_factory=list)
    suppressed_protocols: list[str] = field(default_factory=list)
    guideline_refs: list[dict[str, str]] = field(default_factory=list)
    risk_level: str = "medium"
    perturbation_types: list[str] = field(default_factory=list)

    @classmethod
    def from_routing_case(cls, case: RoutingCase) -> DownstreamCase:
        return cls(
            id=case.id,
            raw_input=case.raw_input,
            canonical_input=case.canonical_input,
            expected_protocol_id=case.expected_protocol_id,
            expected_route=case.expected_route,
            positive_risks=list(case.positive_risks),
            negated_risks=list(case.negated_risks),
            primary_intent=case.primary_intent,
            secondary_intents=list(case.secondary_intents),
            operational_constraints=list(case.operational_constraints),
            should_not_trigger=list(case.should_not_trigger),
            suppressed_protocols=list(case.suppressed_protocols),
            guideline_refs=[dict(ref) for ref in case.guideline_refs],
            risk_level=case.risk_level,
            perturbation_types=list(case.perturbation_types),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownstreamCase:
        if not isinstance(data, dict):
            msg = "downstream case must be a JSON object"
            raise ValueError(msg)
        return cls(
            id=str(data.get("id") or ""),
            raw_input=str(data.get("raw_input") or ""),
            canonical_input=str(
                data.get("canonical_input") or data.get("raw_input") or ""
            ),
            expected_protocol_id=_optional_str(data.get("expected_protocol_id")),
            expected_route=str(data.get("expected_route") or ""),
            positive_risks=_list_of_str(data, "positive_risks"),
            negated_risks=_list_of_str(data, "negated_risks"),
            primary_intent=str(data.get("primary_intent") or ""),
            secondary_intents=_list_of_str(data, "secondary_intents"),
            operational_constraints=_list_of_str(data, "operational_constraints"),
            should_not_trigger=_list_of_str(data, "should_not_trigger"),
            suppressed_protocols=_list_of_str(data, "suppressed_protocols")
            or _list_of_str(data, "should_not_trigger"),
            guideline_refs=_list_of_guideline_refs(data.get("guideline_refs")),
            risk_level=str(data.get("risk_level") or "medium"),
            perturbation_types=_list_of_str(data, "perturbation_types"),
        )

    @classmethod
    def from_json_line(cls, line: str) -> DownstreamCase:
        return cls.from_dict(json.loads(line))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievedEvidence:
    rank: int
    chunk_id: str
    text: str
    source_id: str
    protocol_id: str | None = None
    route: str = ""
    risk: str = ""
    score: float = 0.0
    matched_gold_protocol: bool = False
    matched_guideline_ref: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DownstreamPrediction:
    id: str
    system: str
    raw_input: str
    retrieval_query: str
    risk_context: dict[str, Any] = field(default_factory=dict)
    retrieved_evidence: list[RetrievedEvidence] = field(default_factory=list)
    predicted_protocol_id: str | None = None
    protocol_acc: float = 0.0
    evidence_hit_at_1: float = 0.0
    evidence_hit_at_3: float = 0.0
    pftr: float = 0.0
    hrr_hit: float = 0.0
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "system": self.system,
            "raw_input": self.raw_input,
            "retrieval_query": self.retrieval_query,
            "risk_context": dict(self.risk_context),
            "retrieved_evidence": [
                evidence.to_dict() for evidence in self.retrieved_evidence
            ],
            "predicted_protocol_id": self.predicted_protocol_id,
            "protocol_acc": self.protocol_acc,
            "evidence_hit_at_1": self.evidence_hit_at_1,
            "evidence_hit_at_3": self.evidence_hit_at_3,
            "pftr": self.pftr,
            "hrr_hit": self.hrr_hit,
            "trace": dict(self.trace),
        }


@dataclass
class GenerationOutput:
    id: str
    system: str
    raw_input: str
    prompt: str
    answer: str
    model: str
    risk_context: dict[str, Any] = field(default_factory=dict)
    retrieved_evidence: list[RetrievedEvidence] = field(default_factory=list)
    predicted_protocol_id: str | None = None
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "system": self.system,
            "raw_input": self.raw_input,
            "prompt": self.prompt,
            "answer": self.answer,
            "model": self.model,
            "risk_context": dict(self.risk_context),
            "retrieved_evidence": [
                evidence.to_dict() for evidence in self.retrieved_evidence
            ],
            "predicted_protocol_id": self.predicted_protocol_id,
            "trace": dict(self.trace),
        }


@dataclass
class EvaluationResult:
    id: str
    system: str
    metrics: dict[str, float] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _list_of_str(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list):
        msg = f"{field_name} must be list[str]"
        raise ValueError(msg)
    if not all(isinstance(item, str) for item in value):
        msg = f"{field_name} must contain only strings"
        raise ValueError(msg)
    return list(value)


def _list_of_guideline_refs(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        msg = "guideline_refs must be list[dict[str, str]]"
        raise ValueError(msg)
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            msg = "guideline_refs must contain objects"
            raise ValueError(msg)
        refs.append(
            {str(key): str(val) for key, val in item.items() if val is not None}
        )
    return refs
