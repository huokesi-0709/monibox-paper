from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from runtime.intent_extractor import INTENT_PRIORITY

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
KNOWN_PRIMARY_INTENTS = set(INTENT_PRIORITY)
LIST_FIELD_NAMES = ("expected_tags", "gold_chunk_ids", "unsafe_actions")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _list_of_str(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be list[str]")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must contain only strings")
    return list(value)


@dataclass
class BenchmarkCase:
    id: str
    query: str
    clean_id: str | None = None
    canonical_id: str | None = None
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
        if not isinstance(data, dict):
            raise ValueError("benchmark case must be a JSON object")
        case = BenchmarkCase(
            id=str(data.get("id") or ""),
            query=str(data.get("query") or ""),
            clean_id=_optional_str(data.get("clean_id")),
            canonical_id=_optional_str(data.get("canonical_id")),
            clean_query=_optional_str(data.get("clean_query")),
            perturbation_type=_optional_str(data.get("perturbation_type")),
            risk_level=_optional_str(data.get("risk_level")),
            expected_route=_optional_str(data.get("expected_route")),
            expected_protocol_id=_optional_str(data.get("expected_protocol_id")),
            expected_primary_intent=_optional_str(data.get("expected_primary_intent")),
            expected_tags=_list_of_str(data, "expected_tags"),
            gold_chunk_ids=_list_of_str(data, "gold_chunk_ids"),
            unsafe_actions=_list_of_str(data, "unsafe_actions"),
            reference_reply=_optional_str(data.get("reference_reply")),
        )
        case.validate()
        return case

    def validate(self, context: str = "") -> None:
        label = f"{context}: " if context else ""
        case_label = self.id or "<missing>"
        if not self.id.strip():
            raise ValueError(f"{label}case {case_label}: id must be non-empty")
        if not self.query.strip():
            raise ValueError(f"{label}case {case_label}: query must be non-empty")
        if self.risk_level:
            risk_level = self.risk_level.lower()
            if risk_level not in VALID_RISK_LEVELS:
                allowed = ", ".join(sorted(VALID_RISK_LEVELS))
                raise ValueError(
                    f"{label}case {case_label}: risk_level must be one of {allowed}"
                )
        if (
            self.expected_primary_intent
            and self.expected_primary_intent not in KNOWN_PRIMARY_INTENTS
        ):
            raise ValueError(
                f"{label}case {case_label}: expected_primary_intent "
                f"must be one of known intents"
            )
        for field_name in LIST_FIELD_NAMES:
            value = getattr(self, field_name)
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(
                    f"{label}case {case_label}: {field_name} must be list[str]"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "clean_id": self.clean_id,
            "canonical_id": self.canonical_id,
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
    resolved = _resolve(path)
    for lineno, line in enumerate(
        resolved.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            case = BenchmarkCase.from_dict(json.loads(line))
            case.validate(context=f"{resolved}:line {lineno}")
        except ValueError as exc:
            raise ValueError(f"{resolved}:line {lineno}: {exc}") from exc
        cases.append(case)
    return cases
