from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


@dataclass
class TraceTopChunk:
    rank: int | None = None
    chunk_id: str | None = None
    display_id: str | None = None
    source_id: str | None = None
    category: str | None = None
    sub_category: str | None = None
    tags_flat: str | None = None
    text_preview: str | None = None
    distance: float | None = None
    final_distance: float | None = None
    quality_score: float | None = None
    risk: str | None = None
    scene: str | None = None
    score_breakdown: dict[str, Any] | None = None


@dataclass
class InteractionTrace:
    trace_version: str = "paper-trace-v1"
    query_id: str | None = None
    case_id: str | None = None
    suite: str | None = None
    method: str | None = None
    profile: str | None = None
    policy: str | None = None
    ablation: str | None = None
    decision: str | None = None
    low_evidence: bool | None = None
    raw_text: str | None = None
    canonical_text: str | None = None
    corrections: list[dict[str, Any]] = field(default_factory=list)
    input_normalization: dict[str, Any] = field(default_factory=dict)
    route: dict[str, Any] | None = None
    intent_context: dict[str, Any] = field(default_factory=dict)
    primary_intent: str | None = None
    secondary_intents: list[str] = field(default_factory=list)
    risk_score: float | None = None
    protocol_match: dict[str, Any] = field(default_factory=dict)
    protocol_id: str | None = None
    protocol_confidence: float | None = None
    protocol_matched_terms: list[Any] = field(default_factory=list)
    protocol_match_reason: list[str] = field(default_factory=list)
    evidence_score: float | None = None
    top_chunks: list[TraceTopChunk | dict[str, Any]] = field(default_factory=list)
    output_guard: dict[str, Any] = field(default_factory=dict)
    guard_result: dict[str, Any] = field(default_factory=dict)
    guard_level: str | None = None
    guard_reasons: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    reply: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if dataclass_is_instance(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def dataclass_is_instance(value: Any) -> bool:
    return hasattr(value, "__dataclass_fields__") and not isinstance(value, type)


def trace_to_dict(trace: InteractionTrace | dict[str, Any]) -> dict[str, Any]:
    if isinstance(trace, dict):
        return _json_safe(trace)
    return _json_safe(asdict(trace))


def append_trace_jsonl(path: str | Path, trace: InteractionTrace | dict[str, Any]) -> None:
    trace_path = Path(path)
    if not trace_path.is_absolute():
        trace_path = PROJECT_ROOT / trace_path
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace_to_dict(trace), ensure_ascii=False, sort_keys=True))
        f.write("\n")
