from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


@dataclass
class TraceTopChunk:
    chunk_id: str | None = None
    display_id: str | None = None
    distance: float | None = None
    final_distance: float | None = None
    quality_score: float | None = None
    risk: str | None = None
    scene: str | None = None
    score_breakdown: dict[str, Any] | None = None


@dataclass
class InteractionTrace:
    query_id: str | None = None
    raw_text: str | None = None
    canonical_text: str | None = None
    corrections: list[dict[str, Any]] = field(default_factory=list)
    route: dict[str, Any] | None = None
    primary_intent: str | None = None
    secondary_intents: list[str] = field(default_factory=list)
    risk_score: float | None = None
    protocol_id: str | None = None
    protocol_confidence: float | None = None
    evidence_score: float | None = None
    top_chunks: list[TraceTopChunk | dict[str, Any]] = field(default_factory=list)
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
