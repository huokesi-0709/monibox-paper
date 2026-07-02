from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from runtime.intent_extractor import NEGATION_BOUNDARIES, NEGATION_WORDS
from runtime.multi_intent_router import DEFAULT_INTENT_WEIGHTS


@dataclass(frozen=True)
class RoutingPolicy:
    negation_window: int = 6
    negation_penalty: float = 0.45
    negation_words: tuple[str, ...] = NEGATION_WORDS
    boundary_terms: tuple[str, ...] = NEGATION_BOUNDARIES
    intent_base_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_INTENT_WEIGHTS)
    )
    confidence_threshold: float = 0.25
    confidence_thresholds: dict[str, float] = field(default_factory=dict)
    high_risk_boost: float = 0.05
    operational_constraint_weight: float = 0.20

    @staticmethod
    def from_file(path: str | Path) -> RoutingPolicy:
        resolved = Path(path)
        text = resolved.read_text(encoding="utf-8")
        if resolved.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = parse_simple_yaml(text)
        if not isinstance(data, dict):
            raise ValueError(f"{resolved}: policy must be an object")
        return RoutingPolicy.from_dict(data)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RoutingPolicy:
        weights = dict(DEFAULT_INTENT_WEIGHTS)
        weights.update(
            {
                str(key): float(value)
                for key, value in dict(data.get("intent_base_weights") or {}).items()
            }
        )
        return RoutingPolicy(
            negation_window=int(value_or_default(data, "negation_window", 6)),
            negation_penalty=float(value_or_default(data, "negation_penalty", 0.45)),
            negation_words=tuple(
                str(item) for item in data.get("negation_words", NEGATION_WORDS)
            ),
            boundary_terms=tuple(
                str(item) for item in data.get("boundary_terms", NEGATION_BOUNDARIES)
            ),
            intent_base_weights=weights,
            confidence_threshold=float(
                value_or_default(data, "confidence_threshold", 0.25)
            ),
            confidence_thresholds={
                str(key): float(value)
                for key, value in dict(data.get("confidence_thresholds") or {}).items()
            },
            high_risk_boost=float(value_or_default(data, "high_risk_boost", 0.05)),
            operational_constraint_weight=float(
                value_or_default(data, "operational_constraint_weight", 0.20)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["negation_words"] = list(self.negation_words)
        data["boundary_terms"] = list(self.boundary_terms)
        return data


def parse_simple_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key = ""
    for raw_line in text.splitlines():
        line = strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"unsupported YAML line: {raw_line}")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if indent == 0:
            if raw_value == "":
                data[key] = {}
                current_key = key
            else:
                data[key] = parse_scalar(raw_value)
                current_key = ""
        elif current_key:
            parent = data.setdefault(current_key, {})
            if not isinstance(parent, dict):
                raise ValueError(f"YAML key {current_key} is not a mapping")
            parent[key] = parse_scalar(raw_value)
        else:
            raise ValueError(f"nested YAML line without parent: {raw_line}")
    return data


def strip_comment(line: str) -> str:
    in_quote = False
    quote_char = ""
    output: list[str] = []
    for char in line:
        if char in {"'", '"'}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
        if char == "#" and not in_quote:
            break
        output.append(char)
    return "".join(output)


def value_or_default(data: dict[str, Any], key: str, default: Any) -> Any:
    value = data.get(key, default)
    return default if value is None else value


def parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(item.strip()) for item in inner.split(",")]
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
