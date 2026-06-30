from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from benchmarks.rair_rag.routing_schema import RoutingCase
from benchmarks.rair_rag.scripts.generate_candidates import (
    RISK_LEVEL_BY_INTENT,
    expected_tags,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROUND_DIR = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "annotation_rounds"
)
DATA_DIR = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data"
REPORT_DIR = PROJECT_ROOT / "benchmarks" / "rair_rag" / "reports"
DEFAULT_CANDIDATES = DATA_DIR / "candidates" / "rair_candidates.jsonl"
DEFAULT_ADJUDICATION = ROUND_DIR / "adjudication_sheet.csv"
DEFAULT_ANN_A = ROUND_DIR / "round1_annotator_A.csv"
DEFAULT_ANN_B = ROUND_DIR / "round1_annotator_B.csv"
DEFAULT_METRICS = REPORT_DIR / "agreement_metrics.json"
DEFAULT_OUT = DATA_DIR / "gold" / "rair_gold_all.jsonl"
DEFAULT_DISTRIBUTION = DATA_DIR / "gold" / "label_distribution.json"
DEFAULT_TAXONOMY = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "annotation" / "risk_taxonomy.yaml"
)

ANNOTATION_COMPARISON_FIELDS = {
    "human_accept": "human_accept",
    "primary_intent": "annotator_primary_intent",
    "secondary_intents": "annotator_secondary_intents",
    "negated_risks": "annotator_negated_risks",
    "operational_constraints": "annotator_operational_constraints",
    "should_not_trigger": "annotator_should_not_trigger",
}

NON_POSITIVE_RISK_LABELS = {"low_battery", "out_of_scope", "needs_adjudication"}
UNRESOLVED_ACCEPT_VALUES = {"", "needs_adjudication"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RAIR-RAG gold JSONL from consensus and adjudicated labels."
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--adjudication", type=Path, default=DEFAULT_ADJUDICATION)
    parser.add_argument("--ann-a", type=Path, default=DEFAULT_ANN_A)
    parser.add_argument("--ann-b", type=Path, default=DEFAULT_ANN_B)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--distribution", type=Path, default=DEFAULT_DISTRIBUTION)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = build_gold_jsonl(
        candidates_path=args.candidates,
        adjudication_path=args.adjudication,
        ann_a_path=args.ann_a,
        ann_b_path=args.ann_b,
        metrics_path=args.metrics,
        taxonomy_path=args.taxonomy,
        out_path=args.out,
        distribution_path=args.distribution,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def build_gold_jsonl(
    *,
    candidates_path: Path,
    adjudication_path: Path,
    ann_a_path: Path,
    ann_b_path: Path,
    metrics_path: Path,
    taxonomy_path: Path,
    out_path: Path,
    distribution_path: Path,
    overwrite: bool,
) -> dict[str, int]:
    ensure_outputs_available([out_path, distribution_path], overwrite=overwrite)

    candidates = read_jsonl_indexed(candidates_path)
    taxonomy = read_taxonomy(taxonomy_path)
    ann_a_rows = read_csv_indexed(ann_a_path)
    ann_b_rows = read_csv_indexed(ann_b_path)
    adjudication_rows = read_csv_indexed(adjudication_path)
    disagreement_ids = set(read_disagreement_ids(metrics_path))

    cases: list[RoutingCase] = []
    skipped_consensus = Counter()
    skipped_adjudicated = Counter()

    common_ids = sorted(set(candidates) & set(ann_a_rows) & set(ann_b_rows))
    for item_id in common_ids:
        if item_id in disagreement_ids:
            continue
        ann_a = ann_a_rows[item_id]
        ann_b = ann_b_rows[item_id]
        require_consensus(item_id, ann_a, ann_b)
        human_accept = clean(ann_a.get("human_accept"))
        if human_accept != "yes":
            skipped_consensus[human_accept or "blank"] += 1
            continue
        cases.append(
            case_from_consensus(
                item_id=item_id,
                candidate=candidates[item_id],
                annotation=ann_a,
                taxonomy=taxonomy,
            )
        )

    for item_id in sorted(disagreement_ids):
        if item_id not in candidates:
            raise ValueError(f"{candidates_path}: missing disagreement id {item_id}")
        if item_id not in adjudication_rows:
            raise ValueError(f"{adjudication_path}: missing disagreement id {item_id}")
        row = adjudication_rows[item_id]
        final_human_accept = clean(row.get("final_human_accept"))
        if final_human_accept in UNRESOLVED_ACCEPT_VALUES:
            raise ValueError(
                f"{adjudication_path}: {item_id} is missing resolved final_human_accept"
            )
        if final_human_accept != "yes":
            skipped_adjudicated[final_human_accept] += 1
            continue
        cases.append(
            case_from_adjudication(
                item_id=item_id,
                candidate=candidates[item_id],
                adjudication=row,
                adjudication_path=adjudication_path,
                taxonomy=taxonomy,
            )
        )

    write_jsonl(out_path, cases)
    write_distribution(distribution_path, cases)
    return {
        "gold_cases": len(cases),
        "consensus_cases": sum(
            1 for case in cases if case.label_status == "consensus"
        ),
        "adjudicated_cases": sum(
            1 for case in cases if case.label_status == "adjudicated"
        ),
        "skipped_consensus_cases": sum(skipped_consensus.values()),
        "skipped_adjudicated_cases": sum(skipped_adjudicated.values()),
    }


def ensure_outputs_available(paths: list[Path], *, overwrite: bool) -> None:
    if overwrite:
        return
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"output already exists; pass --overwrite: {joined}")


def read_jsonl_indexed(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"{path}:line {line_number}: expected JSON object")
        item_id = clean(item.get("id"))
        if not item_id:
            raise ValueError(f"{path}:line {line_number}: missing id")
        if item_id in rows:
            raise ValueError(f"{path}: duplicate id {item_id}")
        rows[item_id] = item
    return rows


def read_csv_indexed(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    output: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        item_id = clean(row.get("id"))
        if not item_id:
            raise ValueError(f"{path}: row {index} is missing id")
        if item_id in output:
            raise ValueError(f"{path}: duplicate id {item_id}")
        output[item_id] = {key: clean(value) for key, value in row.items()}
    return output


def read_disagreement_ids(path: Path) -> list[str]:
    metrics: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    ids = metrics.get("all_disagreement_ids")
    if not isinstance(ids, list):
        raise ValueError(f"{path}: missing list all_disagreement_ids")
    return [clean(str(item_id)) for item_id in ids if clean(str(item_id))]


def read_taxonomy(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    labels = data.get("risk_labels")
    if not isinstance(labels, dict):
        raise ValueError(f"{path}: missing risk_labels mapping")
    return labels


def require_consensus(
    item_id: str, ann_a: dict[str, str], ann_b: dict[str, str]
) -> None:
    for logical_name, column_name in ANNOTATION_COMPARISON_FIELDS.items():
        if ann_a.get(column_name, "") != ann_b.get(column_name, ""):
            raise ValueError(
                f"{item_id}: {logical_name} differs but is absent from "
                "agreement_metrics.all_disagreement_ids"
            )


def case_from_consensus(
    *,
    item_id: str,
    candidate: dict[str, Any],
    annotation: dict[str, str],
    taxonomy: dict[str, dict[str, Any]],
) -> RoutingCase:
    primary_intent = require_value(
        annotation.get("annotator_primary_intent"),
        field_name="annotator_primary_intent",
        item_id=item_id,
    )
    secondary_intents = split_labels(annotation.get("annotator_secondary_intents", ""))
    negated_risks = split_labels(annotation.get("annotator_negated_risks", ""))
    operational_constraints = split_labels(
        annotation.get("annotator_operational_constraints", "")
    )
    should_not_trigger = split_labels(
        annotation.get("annotator_should_not_trigger", "")
    )
    return build_case(
        item_id=item_id,
        candidate=candidate,
        raw_input=clean(candidate.get("raw_input")),
        canonical_input=clean(candidate.get("canonical_input")),
        primary_intent=primary_intent,
        secondary_intents=secondary_intents,
        negated_risks=negated_risks,
        operational_constraints=operational_constraints,
        should_not_trigger=should_not_trigger,
        expected_route=clean(candidate.get("expected_route")),
        expected_protocol_id=clean(candidate.get("expected_protocol_id")) or None,
        risk_level=clean(candidate.get("risk_level"))
        or RISK_LEVEL_BY_INTENT.get(primary_intent, "medium"),
        label_status="consensus",
        taxonomy=taxonomy,
    )


def case_from_adjudication(
    *,
    item_id: str,
    candidate: dict[str, Any],
    adjudication: dict[str, str],
    adjudication_path: Path,
    taxonomy: dict[str, dict[str, Any]],
) -> RoutingCase:
    primary_intent = require_value(
        adjudication.get("final_primary_intent"),
        field_name="final_primary_intent",
        item_id=item_id,
        path=adjudication_path,
    )
    raw_input = clean(adjudication.get("final_raw_input")) or clean(
        candidate.get("raw_input")
    )
    return build_case(
        item_id=item_id,
        candidate=candidate,
        raw_input=raw_input,
        canonical_input=raw_input,
        primary_intent=primary_intent,
        secondary_intents=split_labels(adjudication.get("final_secondary_intents", "")),
        negated_risks=split_labels(adjudication.get("final_negated_risks", "")),
        operational_constraints=split_labels(
            adjudication.get("final_operational_constraints", "")
        ),
        should_not_trigger=split_labels(
            adjudication.get("final_should_not_trigger", "")
        ),
        expected_route=clean(adjudication.get("final_expected_route"))
        or clean(candidate.get("expected_route")),
        expected_protocol_id=clean(adjudication.get("final_expected_protocol_id"))
        or clean(candidate.get("expected_protocol_id"))
        or None,
        risk_level=clean(adjudication.get("final_risk_level"))
        or clean(candidate.get("risk_level"))
        or RISK_LEVEL_BY_INTENT.get(primary_intent, "medium"),
        label_status="adjudicated",
        safety_note=clean(adjudication.get("final_notes"))
        or clean(adjudication.get("adjudicator_notes"))
        or None,
        taxonomy=taxonomy,
    )


def build_case(
    *,
    item_id: str,
    candidate: dict[str, Any],
    raw_input: str,
    canonical_input: str,
    primary_intent: str,
    secondary_intents: list[str],
    negated_risks: list[str],
    operational_constraints: list[str],
    should_not_trigger: list[str],
    expected_route: str,
    expected_protocol_id: str | None,
    risk_level: str,
    label_status: str,
    taxonomy: dict[str, dict[str, Any]],
    safety_note: str | None = None,
) -> RoutingCase:
    positive_risks = positive_risks_for(
        primary_intent=primary_intent,
        secondary_intents=secondary_intents,
        operational_constraints=operational_constraints,
        negated_risks=negated_risks,
    )
    data = dict(candidate)
    data.update(
        {
            "id": item_id,
            "raw_input": raw_input,
            "canonical_input": canonical_input or raw_input,
            "source_type": "template_generated_human_reviewed",
            "guideline_refs": guideline_refs_for_case(
                taxonomy=taxonomy,
                primary_intent=primary_intent,
                positive_risks=positive_risks,
                secondary_intents=secondary_intents,
                negated_risks=negated_risks,
                operational_constraints=operational_constraints,
            ),
            "risk_mentions": risk_mentions_for_case(
                taxonomy=taxonomy,
                text=canonical_input or raw_input,
                primary_intent=primary_intent,
                positive_risks=positive_risks,
                secondary_intents=secondary_intents,
                negated_risks=negated_risks,
                operational_constraints=operational_constraints,
            ),
            "positive_risks": positive_risks,
            "negated_risks": negated_risks,
            "primary_intent": primary_intent,
            "secondary_intents": secondary_intents,
            "operational_constraints": operational_constraints,
            "expected_route": expected_route,
            "expected_protocol_id": expected_protocol_id,
            "should_not_trigger": should_not_trigger,
            "risk_level": risk_level,
            "expected_tags": expected_tags(
                primary_intent=primary_intent,
                positive_risks=positive_risks,
                secondary_intents=secondary_intents,
                operational_constraints=operational_constraints,
            ),
            "safety_note": safety_note,
            "label_status": label_status,
        }
    )
    return RoutingCase.from_dict(data)


def guideline_refs_for_case(
    *,
    taxonomy: dict[str, dict[str, Any]],
    primary_intent: str,
    positive_risks: list[str],
    secondary_intents: list[str],
    negated_risks: list[str],
    operational_constraints: list[str],
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for label in evidence_labels(
        primary_intent=primary_intent,
        positive_risks=positive_risks,
        secondary_intents=secondary_intents,
        negated_risks=negated_risks,
        operational_constraints=operational_constraints,
    ):
        config = taxonomy.get(label) or {}
        review_status = clean(config.get("review_status")) or "unspecified"
        for basis in config.get("guideline_basis") or []:
            if not isinstance(basis, dict):
                continue
            source_id = clean(basis.get("source_id"))
            section = clean(basis.get("section"))
            if not source_id:
                continue
            key = (label, source_id, section)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "risk_label": label,
                    "source_id": source_id,
                    "section": section,
                    "review_status": review_status,
                }
            )
    return refs


def risk_mentions_for_case(
    *,
    taxonomy: dict[str, dict[str, Any]],
    text: str,
    primary_intent: str,
    positive_risks: list[str],
    secondary_intents: list[str],
    negated_risks: list[str],
    operational_constraints: list[str],
) -> list[str]:
    mentions: list[str] = []
    for label in evidence_labels(
        primary_intent=primary_intent,
        positive_risks=positive_risks,
        secondary_intents=secondary_intents,
        negated_risks=negated_risks,
        operational_constraints=operational_constraints,
    ):
        triggers = taxonomy.get(label, {}).get("positive_triggers") or []
        matched = [
            str(trigger)
            for trigger in triggers
            if trigger and str(trigger) in text
        ]
        if matched:
            for trigger in matched:
                item = f"{label}:{trigger}"
                if item not in mentions:
                    mentions.append(item)
        else:
            item = f"inferred:{label}"
            if item not in mentions:
                mentions.append(item)
    return mentions


def evidence_labels(
    *,
    primary_intent: str,
    positive_risks: list[str],
    secondary_intents: list[str],
    negated_risks: list[str],
    operational_constraints: list[str],
) -> list[str]:
    labels: list[str] = []
    for label in [
        primary_intent,
        *positive_risks,
        *secondary_intents,
        *negated_risks,
        *operational_constraints,
    ]:
        if label and label not in labels:
            labels.append(label)
    return labels


def positive_risks_for(
    *,
    primary_intent: str,
    secondary_intents: list[str],
    operational_constraints: list[str],
    negated_risks: list[str],
) -> list[str]:
    blocked = set(operational_constraints) | set(negated_risks)
    output: list[str] = []
    for label in [primary_intent, *secondary_intents]:
        if label in blocked or label in NON_POSITIVE_RISK_LABELS:
            continue
        if label and label not in output:
            output.append(label)
    return output


def require_value(
    value: str | None, *, field_name: str, item_id: str, path: Path | None = None
) -> str:
    cleaned = clean(value)
    if cleaned:
        return cleaned
    prefix = f"{path}: " if path else ""
    raise ValueError(f"{prefix}{item_id} is missing {field_name}")


def split_labels(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(";", "|").replace(",", "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def clean(value: Any) -> str:
    return (value or "").strip()


def write_jsonl(path: Path, cases: list[RoutingCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True)
        for case in cases
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_distribution(path: Path, cases: list[RoutingCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    distribution = {
        "num_cases": len(cases),
        "perturbation_type": count_list_values(
            case.perturbation_types for case in cases
        ),
        "primary_intent": dict(
            sorted(Counter(case.primary_intent for case in cases).items())
        ),
        "risk_level": dict(sorted(Counter(case.risk_level for case in cases).items())),
        "source_type": dict(
            sorted(Counter(case.source_type for case in cases).items())
        ),
        "label_status": dict(
            sorted(Counter(case.label_status for case in cases).items())
        ),
    }
    path.write_text(
        json.dumps(distribution, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def count_list_values(values: Any) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for items in values:
        counter.update(items)
    return dict(sorted(counter.items()))


if __name__ == "__main__":
    main()
