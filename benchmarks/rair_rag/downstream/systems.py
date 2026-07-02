from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from benchmarks.rair_rag.baselines.bert_multilabel_predictor import (
    BertMultilabelPredictor,
)
from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence
from runtime.rag_engine import RagEngine, SearchResult
from runtime.risk_router import (
    RiskAwareInputRouter,
    protocol_for_route,
    route_for_intent,
)


@dataclass
class DownstreamSystem(ABC):
    name: str
    last_trace: dict[str, Any] = field(default_factory=dict, init=False)

    @abstractmethod
    def build_context(self, case: DownstreamCase) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def build_retrieval_query(
        self, case: DownstreamCase, context: dict[str, Any]
    ) -> str:
        raise NotImplementedError

    def retrieve(
        self, case: DownstreamCase, rag_engine: RagEngine, topk: int = 5
    ) -> list[RetrievedEvidence]:
        context = self.build_context(case)
        query = self.build_retrieval_query(case, context)
        search_topk = topk
        suppressed_protocols = _list_of_str(context.get("suppressed_protocols"))
        if suppressed_protocols:
            search_topk = max(topk * 3, topk + len(suppressed_protocols))

        raw_results = rag_engine.search(
            query=query, topk=search_topk, intent_context=context or None
        )
        evidence, filter_trace = _to_evidence_list(
            raw_results=raw_results,
            topk=topk,
            case=case,
            suppressed_protocols=suppressed_protocols,
        )
        self.last_trace = {
            "system": self.name,
            "retrieval_query": query,
            "risk_context": context,
            "raw_result_count": len(raw_results),
            "returned_result_count": len(evidence),
            "suppression": filter_trace,
        }
        return evidence


@dataclass
class VanillaRagSystem(DownstreamSystem):
    name: str = "vanilla-rag"

    def build_context(self, case: DownstreamCase) -> dict[str, Any]:
        return {"trace": {"system": self.name, "risk_context_used": False}}

    def build_retrieval_query(
        self, case: DownstreamCase, context: dict[str, Any]
    ) -> str:
        return case.raw_input


@dataclass
class KeywordRagSystem(DownstreamSystem):
    name: str = "keyword-rag"
    router: RiskAwareInputRouter = field(default_factory=RiskAwareInputRouter)

    def build_context(self, case: DownstreamCase) -> dict[str, Any]:
        mentions = self.router.extract_risk_mentions(case.canonical_input)
        first = mentions[0] if mentions else {}
        primary = str(first.get("risk") or "out_of_scope")
        route = route_for_intent(primary)
        protocol_id = protocol_for_route(route)
        return {
            "primary_intent": primary,
            "secondary_intents": [],
            "positive_risks": [] if primary == "out_of_scope" else [primary],
            "negated_risks": [],
            "operational_constraints": ["low_battery"]
            if primary == "low_battery"
            else [],
            "suppressed_protocols": [],
            "predicted_route": route,
            "protocol_id": protocol_id,
            "risk_score": float(first.get("confidence") or 0.05),
            "trace": {
                "system": self.name,
                "baseline": "first textual keyword match",
                "risk_mentions": mentions,
            },
        }

    def build_retrieval_query(
        self, case: DownstreamCase, context: dict[str, Any]
    ) -> str:
        return _join_query_parts(
            [
                case.raw_input,
                context.get("primary_intent"),
                context.get("predicted_route"),
                context.get("protocol_id"),
            ]
        )


@dataclass
class BertRagSystem(DownstreamSystem):
    name: str = "bert-rag"
    threshold: float | None = None
    model_dir: Any = None
    predictor: BertMultilabelPredictor = field(init=False)

    def __post_init__(self) -> None:
        self.predictor = BertMultilabelPredictor(
            model_dir=self.model_dir,
            threshold=self.threshold,
        )

    def build_context(self, case: DownstreamCase) -> dict[str, Any]:
        context = self.predictor.predict_context(case.raw_input or case.canonical_input)
        trace = dict(context.get("trace") or {})
        trace["system"] = self.name
        context["trace"] = trace
        return context

    def build_retrieval_query(
        self, case: DownstreamCase, context: dict[str, Any]
    ) -> str:
        return _join_query_parts(
            [
                case.raw_input,
                context.get("primary_intent"),
                context.get("secondary_intents"),
                context.get("positive_risks"),
                context.get("predicted_route"),
                context.get("protocol_id"),
            ]
        )


@dataclass
class RairRagSystem(DownstreamSystem):
    name: str = "rair-rag"
    router: RiskAwareInputRouter = field(default_factory=RiskAwareInputRouter)

    def build_context(self, case: DownstreamCase) -> dict[str, Any]:
        routing_context = self.router.route(case.raw_input, case.canonical_input)
        context = routing_context.to_retrieval_context()
        context["trace"] = {
            "system": self.name,
            "router_trace": routing_context.trace,
            "risk_context_fields": [
                "primary_intent",
                "secondary_intents",
                "predicted_route",
                "protocol_id",
                "positive_risks",
                "negated_risks",
                "suppressed_protocols",
                "operational_constraints",
            ],
        }
        return context

    def build_retrieval_query(
        self, case: DownstreamCase, context: dict[str, Any]
    ) -> str:
        return _join_query_parts(
            [
                case.raw_input,
                context.get("primary_intent"),
                context.get("secondary_intents"),
                context.get("predicted_route"),
                context.get("protocol_id"),
                context.get("positive_risks"),
                context.get("negated_risks"),
                context.get("operational_constraints"),
            ]
        )


def default_downstream_systems() -> list[DownstreamSystem]:
    return [VanillaRagSystem(), KeywordRagSystem(), BertRagSystem(), RairRagSystem()]


def _to_evidence_list(
    *,
    raw_results: list[SearchResult],
    topk: int,
    case: DownstreamCase,
    suppressed_protocols: list[str],
) -> tuple[list[RetrievedEvidence], dict[str, Any]]:
    evidence: list[RetrievedEvidence] = []
    filtered: list[dict[str, Any]] = []
    for result in raw_results:
        protocol_id = _infer_protocol_id(result)
        suppressed = bool(protocol_id and protocol_id in suppressed_protocols)
        if suppressed:
            filtered.append(
                {
                    "chunk_id": result.chunk_id,
                    "protocol_id": protocol_id,
                    "risk": result.risk,
                    "reason": "suppressed_protocol",
                }
            )
            continue
        evidence.append(
            RetrievedEvidence(
                rank=len(evidence) + 1,
                chunk_id=str(result.chunk_id or ""),
                text=str(result.text or ""),
                source_id=str(result.source_id or ""),
                protocol_id=protocol_id,
                route=_infer_route(result),
                risk=str(result.risk or ""),
                score=_score_from_result(result),
                matched_gold_protocol=bool(
                    case.expected_protocol_id
                    and protocol_id
                    and protocol_id == case.expected_protocol_id
                ),
                matched_guideline_ref=_matches_guideline_ref(result, case),
            )
        )
        if len(evidence) >= topk:
            break

    return evidence, {
        "suppressed_protocols": suppressed_protocols,
        "filtered_results": filtered,
        "weak_protocol_inference": True,
    }


def _infer_protocol_id(result: SearchResult) -> str | None:
    direct = getattr(result, "protocol_id", None)
    if direct:
        return str(direct)

    route = _infer_route(result)
    if route:
        return protocol_for_route(route)

    haystack = _result_haystack(result)
    protocol_ids = {
        "prot_respiratory_distress",
        "prot_bleeding_control",
        "prot_injury_fracture",
        "prot_crush_injury",
        "prot_head_injury",
        "prot_hypothermia",
        "prot_psychological_support",
        "prot_entrapment",
        "prot_aftershock_collapse",
        "prot_resource_deprivation",
    }
    for protocol_id in protocol_ids:
        if protocol_id in haystack:
            return protocol_id
    return None


def _infer_route(result: SearchResult) -> str:
    direct = getattr(result, "route", None)
    if direct:
        return str(direct)
    risk = str(getattr(result, "risk", "") or "")
    route = route_for_intent(risk)
    if route:
        return route
    haystack = _result_haystack(result)
    for risk_label in (
        "respiratory_distress",
        "severe_bleeding_or_shock",
        "trauma_or_fracture",
        "crush_injury",
        "altered_consciousness_or_head_injury",
        "hypothermia",
        "psychological_distress",
        "trapped_or_entrapment",
        "aftershock_or_collapse_hazard",
        "dehydration_or_resource_deprivation",
    ):
        if risk_label in haystack:
            return route_for_intent(risk_label) or ""
    return ""


def _matches_guideline_ref(result: SearchResult, case: DownstreamCase) -> bool:
    result_source = str(result.source_id or "")
    if not result_source:
        return False
    for ref in case.guideline_refs:
        source_id = str(ref.get("source_id") or "")
        if source_id and source_id == result_source:
            return True
    return False


def _score_from_result(result: SearchResult) -> float:
    score = getattr(result, "score", None)
    if score is not None:
        return float(score)
    final_distance = float(getattr(result, "final_distance", 0.0) or 0.0)
    if final_distance <= 0:
        return 0.0
    return 1.0 / (1.0 + final_distance)


def _result_haystack(result: SearchResult) -> str:
    return " ".join(
        str(getattr(result, field_name, "") or "")
        for field_name in (
            "chunk_id",
            "display_id",
            "group_id",
            "category",
            "sub_category",
            "dimension",
            "risk",
            "scene",
            "source_id",
            "tags_flat",
        )
    )


def _join_query_parts(parts: list[Any]) -> str:
    values: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, list):
            values.extend(str(item) for item in part if item)
            continue
        text = str(part).strip()
        if text:
            values.append(text)
    return " ".join(_dedupe(values))


def _list_of_str(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value)]
    return [str(item) for item in value if item]


def _dedupe(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "")
        if item and item not in output:
            output.append(item)
    return output
