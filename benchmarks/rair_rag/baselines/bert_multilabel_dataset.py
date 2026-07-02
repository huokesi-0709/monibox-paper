from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABELS = [
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
    "low_battery",
    "out_of_scope",
]

OPERATIONAL_LABELS = {"low_battery"}
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}
ID_TO_LABEL = {index: label for label, index in LABEL_TO_ID.items()}


@dataclass(frozen=True)
class BertMultilabelExample:
    id: str
    text: str
    labels: list[str]
    target: list[float]
    raw: dict[str, Any]


def load_bert_multilabel_examples(path: Path) -> list[BertMultilabelExample]:
    examples: list[BertMultilabelExample] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            msg = f"{path}:line {lineno}: expected JSON object"
            raise ValueError(msg)
        examples.append(example_from_payload(payload, path=path, lineno=lineno))
    return examples


def example_from_payload(
    payload: dict[str, Any], *, path: Path | None = None, lineno: int | None = None
) -> BertMultilabelExample:
    text = str(payload.get("raw_input") or payload.get("canonical_input") or "")
    if not text.strip():
        location = f"{path}:line {lineno}: " if path and lineno else ""
        msg = f"{location}raw_input and canonical_input are both empty"
        raise ValueError(msg)
    labels = labels_from_payload(payload)
    return BertMultilabelExample(
        id=str(payload.get("id") or ""),
        text=text,
        labels=labels,
        target=target_vector(labels),
        raw=dict(payload),
    )


def labels_from_payload(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(_list_of_str(payload.get("positive_risks")))
    values.extend(_list_of_str(payload.get("operational_constraints")))
    return dedupe(label for label in values if label in LABEL_TO_ID)


def target_vector(labels: list[str]) -> list[float]:
    target = [0.0 for _label in LABELS]
    for label in labels:
        if label in LABEL_TO_ID:
            target[LABEL_TO_ID[label]] = 1.0
    return target


def label_map_payload() -> dict[str, Any]:
    return {
        "labels": list(LABELS),
        "label_to_id": dict(LABEL_TO_ID),
        "id_to_label": {str(key): value for key, value in ID_TO_LABEL.items()},
        "target_source_fields": ["positive_risks", "operational_constraints"],
        "excluded_training_label_fields": [
            "negated_risks",
            "suppressed_protocols",
            "expected_route",
            "expected_protocol_id",
        ],
    }


def write_label_map(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(label_map_payload(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def dedupe(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "")
        if item and item not in output:
            output.append(item)
    return output


def _list_of_str(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value)]
    return [str(item) for item in value if item is not None]
