from __future__ import annotations

import json
from typing import Any

from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence

OUTPUT_FORMAT_INSTRUCTIONS = """
Return only a compact JSON object. Do not wrap it in Markdown.
Required schema:
{
  "protocol_id": "...",
  "reply": "...",
  "safety_notes": ["..."],
  "used_evidence": ["..."]
}
If uncertain, set unknown fields to null or [] and keep "reply" safe and brief.
""".strip()


def build_vanilla_generation_prompt(
    case: DownstreamCase, evidence: list[RetrievedEvidence | dict[str, Any]]
) -> str:
    payload = {
        "task": "Generate a short, safe emergency-assistance reply for voice playback.",
        "user_input": case.raw_input,
        "retrieved_evidence": _evidence_payload(evidence),
        "instructions": [
            "Use only the user input and retrieved evidence.",
            "Do not assume structured RAIR risk context is available.",
            "Give practical, safety-first guidance.",
            "Keep the reply concise and suitable for spoken delivery.",
        ],
    }
    return _build_prompt(payload)


def build_rair_generation_prompt(
    case: DownstreamCase,
    risk_context: dict[str, Any],
    evidence: list[RetrievedEvidence | dict[str, Any]],
) -> str:
    context = _risk_context_payload(risk_context)
    payload = {
        "task": "Generate a short, safe emergency-assistance reply for voice playback.",
        "user_input": case.raw_input,
        "risk_context": context,
        "retrieved_evidence": _evidence_payload(evidence),
        "instructions": [
            "Do not trigger protocols listed in suppressed_protocols.",
            "Do not treat negated_risks as real active risks.",
            "Prioritize the primary_intent when selecting the reply focus.",
            "Preserve operational_constraints in the response strategy.",
            "Use retrieved evidence only when it does not conflict with the risk_context.",
            "Keep the reply concise, safe, and suitable for spoken delivery.",
        ],
    }
    return _build_prompt(payload)


def _build_prompt(payload: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "You are a cautious emergency-assistance response generator.",
            "Follow the experiment input exactly.",
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            OUTPUT_FORMAT_INSTRUCTIONS,
        ]
    )


def _risk_context_payload(risk_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_intent": risk_context.get("primary_intent"),
        "secondary_intents": _list_value(risk_context.get("secondary_intents")),
        "negated_risks": _list_value(risk_context.get("negated_risks")),
        "suppressed_protocols": _list_value(risk_context.get("suppressed_protocols")),
        "operational_constraints": _list_value(
            risk_context.get("operational_constraints")
        ),
        "predicted_route": risk_context.get("predicted_route"),
        "protocol_id": risk_context.get("protocol_id"),
    }


def _evidence_payload(
    evidence: list[RetrievedEvidence | dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_single_evidence_payload(item) for item in evidence]


def _single_evidence_payload(
    evidence: RetrievedEvidence | dict[str, Any],
) -> dict[str, Any]:
    data = evidence.to_dict() if hasattr(evidence, "to_dict") else dict(evidence)
    return {
        "rank": data.get("rank"),
        "chunk_id": data.get("chunk_id"),
        "protocol_id": data.get("protocol_id"),
        "route": data.get("route"),
        "risk": data.get("risk"),
        "source_id": data.get("source_id"),
        "text": data.get("text"),
    }


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]
