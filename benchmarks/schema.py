from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


@dataclass
class BenchmarkCase:
    id: str
    query: str
    clean_query: str | None = None
    perturbation_type: str | None = None
    risk_level: str | None = None
    expected_route: str | None = None
    expected_protocol_id: str | None = None
    expected_primary_intent: str | None = None
    expected_tags: list[str] = field(default_factory=list)
    gold_chunk_ids: list[str] = field(default_factory=list)
    unsafe_actions: list[str] = field(default_factory=list)
    reference_reply: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> BenchmarkCase:
        return BenchmarkCase(
            id=str(data.get("id") or ""),
            query=str(data.get("query") or ""),
            clean_query=data.get("clean_query"),
            perturbation_type=data.get("perturbation_type"),
            risk_level=data.get("risk_level"),
            expected_route=data.get("expected_route"),
            expected_protocol_id=data.get("expected_protocol_id"),
            expected_primary_intent=data.get("expected_primary_intent"),
            expected_tags=list(data.get("expected_tags") or []),
            gold_chunk_ids=list(data.get("gold_chunk_ids") or []),
            unsafe_actions=list(data.get("unsafe_actions") or []),
            reference_reply=data.get("reference_reply"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "clean_query": self.clean_query,
            "perturbation_type": self.perturbation_type,
            "risk_level": self.risk_level,
            "expected_route": self.expected_route,
            "expected_protocol_id": self.expected_protocol_id,
            "expected_primary_intent": self.expected_primary_intent,
            "expected_tags": list(self.expected_tags),
            "gold_chunk_ids": list(self.gold_chunk_ids),
            "unsafe_actions": list(self.unsafe_actions),
            "reference_reply": self.reference_reply,
        }


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def load_cases(path: str | Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for line in _resolve(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(BenchmarkCase.from_dict(json.loads(line)))
    return cases
