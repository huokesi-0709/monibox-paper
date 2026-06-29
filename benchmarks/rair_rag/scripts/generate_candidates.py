from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from string import Formatter
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEMPLATE_DIR = PROJECT_ROOT / "benchmarks" / "rair_rag" / "templates"
DEFAULT_OUT = (
    PROJECT_ROOT
    / "benchmarks"
    / "rair_rag"
    / "data"
    / "candidates"
    / "rair_candidates.jsonl"
)

RISK_LEVEL_BY_INTENT = {
    "respiratory_distress": "critical",
    "severe_bleeding_or_shock": "high",
    "crush_injury": "high",
    "altered_consciousness_or_head_injury": "high",
    "trapped_or_entrapment": "high",
    "aftershock_or_collapse_hazard": "high",
    "hypothermia": "high",
    "trauma_or_fracture": "medium",
    "dehydration_or_resource_deprivation": "medium",
    "psychological_distress": "medium",
    "low_battery": "low",
    "out_of_scope": "low",
}

PROTOCOL_BY_ROUTE = {
    "route_respiratory_distress": "prot_respiratory_distress",
    "route_bleeding_control": "prot_bleeding_control",
    "route_trauma_or_fracture": "prot_injury_fracture",
    "route_crush_injury": "prot_crush_injury",
    "route_head_or_consciousness": "prot_head_injury",
    "route_hypothermia": "prot_hypothermia",
    "route_psychological_support": "prot_psychological_support",
    "route_trapped_or_entrapment": "prot_entrapment",
    "route_aftershock_or_collapse_hazard": "prot_aftershock_collapse",
    "route_dehydration_or_resource_deprivation": "prot_resource_deprivation",
    "route_out_of_scope": None,
}

TAG_BY_INTENT = {
    "respiratory_distress": ["risk_respiratory", "medical_high_risk"],
    "severe_bleeding_or_shock": ["risk_bleeding", "medical_high_risk"],
    "trauma_or_fracture": ["risk_injury"],
    "crush_injury": ["risk_crush", "medical_high_risk"],
    "altered_consciousness_or_head_injury": [
        "risk_consciousness",
        "medical_high_risk",
    ],
    "hypothermia": ["risk_hypothermia"],
    "psychological_distress": ["risk_psychological_distress"],
    "trapped_or_entrapment": ["risk_trapped", "scene_entrapment"],
    "aftershock_or_collapse_hazard": ["risk_aftershock", "scene_collapse"],
    "dehydration_or_resource_deprivation": ["risk_resource_deprivation"],
    "low_battery": ["device_constraint", "risk_low_battery"],
    "out_of_scope": ["out_of_scope"],
}

TEMPLATE_FILES = (
    "negation_templates.yaml",
    "multi_intent_templates.yaml",
    "control_templates.yaml",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate RAIR-RAG candidate JSONL from YAML templates."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE_DIR)
    args = parser.parse_args()

    candidates = generate_candidates(args.template_dir)
    write_jsonl(candidates, args.out)
    print(f"wrote {len(candidates)} candidates to {args.out}")


def generate_candidates(template_dir: Path) -> list[dict[str, Any]]:
    counters: dict[str, int] = defaultdict(int)
    candidates: list[dict[str, Any]] = []
    for template_file in TEMPLATE_FILES:
        path = template_dir / template_file
        for template in load_templates(path):
            prefix = id_prefix_for(template_file, template)
            perturbation_types = perturbation_types_for(template_file, template)
            for variant_index, raw_input in enumerate(expand_template(template), start=1):
                counters[prefix] += 1
                candidate = build_candidate(
                    template=template,
                    raw_input=raw_input,
                    prefix=prefix,
                    sequence=counters[prefix],
                    variant_index=variant_index,
                    perturbation_types=perturbation_types,
                )
                candidates.append(candidate)
    return candidates


def load_templates(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a YAML list")
    templates: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: template #{index} must be an object")
        validate_template(path, index, item)
        templates.append(item)
    return templates


def validate_template(path: Path, index: int, template: dict[str, Any]) -> None:
    required = {
        "template_id",
        "pattern",
        "slots",
        "positive_risks",
        "negated_risks",
        "operational_constraints",
        "primary_intent",
        "secondary_intents",
        "should_not_trigger",
        "notes",
    }
    missing = sorted(required - set(template))
    if missing:
        raise ValueError(f"{path}: template #{index} missing fields: {missing}")
    if not isinstance(template["slots"], dict):
        raise ValueError(f"{path}: template #{index} slots must be an object")
    for slot_name, values in template["slots"].items():
        if not isinstance(slot_name, str):
            raise ValueError(f"{path}: template #{index} slot names must be strings")
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            raise ValueError(
                f"{path}: template #{index} slot {slot_name} must be list[str]"
            )
    for field_name in (
        "positive_risks",
        "negated_risks",
        "operational_constraints",
        "secondary_intents",
        "should_not_trigger",
    ):
        value = template[field_name]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{path}: template #{index} {field_name} must be list[str]")


def expand_template(template: dict[str, Any]) -> list[str]:
    pattern = str(template["pattern"])
    field_names = [name for _, name, _, _ in Formatter().parse(pattern) if name]
    slots: dict[str, list[str]] = template["slots"]
    missing_slots = sorted(set(field_names) - set(slots))
    if missing_slots:
        template_id = template["template_id"]
        raise ValueError(f"{template_id}: missing slots for {missing_slots}")
    if not field_names:
        return [pattern]

    unique_field_names = list(dict.fromkeys(field_names))
    values = [slots[name] for name in unique_field_names]
    expanded: list[str] = []
    for combination in itertools.product(*values):
        mapping = dict(zip(unique_field_names, combination, strict=True))
        expanded.append(pattern.format(**mapping))
    return expanded


def build_candidate(
    template: dict[str, Any],
    raw_input: str,
    prefix: str,
    sequence: int,
    variant_index: int,
    perturbation_types: list[str],
) -> dict[str, Any]:
    template_id = str(template["template_id"])
    primary_intent = str(template["primary_intent"])
    expected_route = template.get("expected_route")
    if expected_route is not None:
        expected_route = str(expected_route)
    expected_protocol_id = PROTOCOL_BY_ROUTE.get(expected_route)
    positive_risks = list(template["positive_risks"])
    negated_risks = list(template["negated_risks"])
    secondary_intents = list(template["secondary_intents"])
    operational_constraints = list(template["operational_constraints"])
    tags = expected_tags(
        primary_intent=primary_intent,
        positive_risks=positive_risks,
        secondary_intents=secondary_intents,
        operational_constraints=operational_constraints,
    )
    return {
        "id": f"{prefix}_{sequence:04d}",
        "canonical_id": f"case_{template_id}",
        "raw_input": raw_input,
        "canonical_input": raw_input,
        "language": "zh-CN",
        "source_type": "template_generated",
        "template_id": template_id,
        "template_variant_index": variant_index,
        "perturbation_types": perturbation_types,
        "positive_risks": positive_risks,
        "negated_risks": negated_risks,
        "operational_constraints": operational_constraints,
        "primary_intent": primary_intent,
        "secondary_intents": secondary_intents,
        "should_not_trigger": list(template["should_not_trigger"]),
        "expected_route": expected_route,
        "expected_protocol_id": expected_protocol_id,
        "risk_level": RISK_LEVEL_BY_INTENT.get(primary_intent, "medium"),
        "expected_tags": tags,
        "label_status": "candidate",
        "needs_human_review": True,
    }


def id_prefix_for(template_file: str, template: dict[str, Any]) -> str:
    if template_file == "negation_templates.yaml":
        return "neg"
    if template_file == "multi_intent_templates.yaml":
        return "multi"
    if template.get("primary_intent") == "out_of_scope":
        return "boundary"
    return "clean"


def perturbation_types_for(
    template_file: str, template: dict[str, Any]
) -> list[str]:
    if template_file == "negation_templates.yaml":
        return ["negation_conflict"]
    if template_file == "multi_intent_templates.yaml":
        return ["multi_intent"]
    if template.get("primary_intent") == "out_of_scope":
        return ["out_of_scope"]
    return ["clean_control"]


def expected_tags(
    primary_intent: str,
    positive_risks: list[str],
    secondary_intents: list[str],
    operational_constraints: list[str],
) -> list[str]:
    tags: list[str] = []
    for intent in [
        primary_intent,
        *positive_risks,
        *secondary_intents,
        *operational_constraints,
    ]:
        for tag in TAG_BY_INTENT.get(intent, []):
            if tag not in tags:
                tags.append(tag)
    return tags


def write_jsonl(candidates: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(candidate, ensure_ascii=False, sort_keys=True)
        for candidate in candidates
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
