from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
LIST_FIELD_NAMES = (
    "guideline_refs",
    "perturbation_types",
    "risk_mentions",
    "positive_risks",
    "negated_risks",
    "secondary_intents",
    "operational_constraints",
    "suppressed_protocols",
    "safety_boundaries",
    "should_not_trigger",
    "expected_tags",
)


@dataclass
class RoutingCase:
    id: str
    canonical_id: str
    raw_input: str
    canonical_input: str
    language: str
    source_type: str
    guideline_refs: list[dict[str, str]] = field(default_factory=list)
    perturbation_types: list[str] = field(default_factory=list)
    risk_mentions: list[str] = field(default_factory=list)
    risk_candidates: list[dict[str, Any]] = field(default_factory=list)
    positive_risks: list[str] = field(default_factory=list)
    negated_risks: list[str] = field(default_factory=list)
    primary_intent: str = ""
    secondary_intents: list[str] = field(default_factory=list)
    operational_constraints: list[str] = field(default_factory=list)
    expected_route: str = ""
    expected_protocol_id: str | None = None
    should_not_trigger: list[str] = field(default_factory=list)
    suppressed_protocols: list[str] = field(default_factory=list)
    safety_boundaries: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    expected_tags: list[str] = field(default_factory=list)
    safety_note: str | None = None
    reference_reply: str | None = None
    label_status: str = "draft"

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RoutingCase:
        if not isinstance(data, dict):
            raise ValueError("routing case must be a JSON object")
        should_not_trigger = _list_of_str(data, "should_not_trigger")
        suppressed_protocols = _list_of_str(data, "suppressed_protocols")
        case = RoutingCase(
            id=str(data.get("id") or ""),
            canonical_id=str(data.get("canonical_id") or ""),
            raw_input=str(data.get("raw_input") or ""),
            canonical_input=str(data.get("canonical_input") or ""),
            language=str(data.get("language") or "zh-CN"),
            source_type=str(data.get("source_type") or ""),
            guideline_refs=_list_of_guideline_refs(data.get("guideline_refs")),
            perturbation_types=_list_of_str(data, "perturbation_types"),
            risk_mentions=_list_of_str(data, "risk_mentions"),
            risk_candidates=_list_of_dict(data, "risk_candidates"),
            positive_risks=_list_of_str(data, "positive_risks"),
            negated_risks=_list_of_str(data, "negated_risks"),
            primary_intent=str(data.get("primary_intent") or ""),
            secondary_intents=_list_of_str(data, "secondary_intents"),
            operational_constraints=_list_of_str(data, "operational_constraints"),
            expected_route=str(data.get("expected_route") or ""),
            expected_protocol_id=_optional_str(data.get("expected_protocol_id")),
            should_not_trigger=should_not_trigger,
            suppressed_protocols=suppressed_protocols or should_not_trigger,
            safety_boundaries=_list_of_str(data, "safety_boundaries"),
            risk_level=str(data.get("risk_level") or "medium"),
            expected_tags=_list_of_str(data, "expected_tags"),
            safety_note=_optional_str(data.get("safety_note")),
            reference_reply=_optional_str(data.get("reference_reply")),
            label_status=str(data.get("label_status") or "draft"),
        )
        case.validate()
        return case

    def validate(self, context: str = "") -> None:
        label = f"{context}: " if context else ""
        case_label = self.id or "<missing>"
        if not self.id.strip():
            raise ValueError(f"{label}case {case_label}: id must be non-empty")
        if not self.raw_input.strip():
            raise ValueError(f"{label}case {case_label}: raw_input must be non-empty")
        if not self.primary_intent.strip():
            raise ValueError(f"{label}case {case_label}: primary_intent must be non-empty")
        if self.risk_level not in VALID_RISK_LEVELS:
            allowed = ", ".join(sorted(VALID_RISK_LEVELS))
            raise ValueError(
                f"{label}case {case_label}: risk_level must be one of {allowed}"
            )
        for field_name in LIST_FIELD_NAMES:
            value = getattr(self, field_name)
            if not isinstance(value, list):
                raise ValueError(f"{label}case {case_label}: {field_name} must be a list")
            if field_name != "guideline_refs" and not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(
                    f"{label}case {case_label}: {field_name} must contain strings"
                )
        for item in self.guideline_refs:
            if not isinstance(item, dict):
                raise ValueError(
                    f"{label}case {case_label}: guideline_refs must contain objects"
                )
            if not item.get("source_id"):
                raise ValueError(
                    f"{label}case {case_label}: guideline_ref.source_id is required"
                )
        if not isinstance(self.risk_candidates, list):
            raise ValueError(
                f"{label}case {case_label}: risk_candidates must be a list"
            )
        if not all(isinstance(item, dict) for item in self.risk_candidates):
            raise ValueError(
                f"{label}case {case_label}: risk_candidates must contain objects"
            )

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
        raise ValueError(f"{field_name} must be list[str]")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must contain only strings")
    return list(value)


def _list_of_dict(data: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    value = data.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be list[dict]")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field_name} must contain only objects")
    return [dict(item) for item in value]


def _list_of_guideline_refs(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("guideline_refs must be list[dict[str, str]]")
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("guideline_refs must contain objects")
        refs.append({str(key): str(val) for key, val in item.items() if val is not None})
    return refs


def load_routing_cases(path: str | Path) -> list[RoutingCase]:
    resolved = Path(path)
    cases: list[RoutingCase] = []
    for lineno, line in enumerate(
        resolved.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            case = RoutingCase.from_dict(json.loads(line))
            case.validate(context=f"{resolved}:line {lineno}")
        except ValueError as exc:
            raise ValueError(f"{resolved}:line {lineno}: {exc}") from exc
        cases.append(case)
    return cases
