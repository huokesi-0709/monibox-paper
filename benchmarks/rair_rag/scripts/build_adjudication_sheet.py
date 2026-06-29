from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROUND_DIR = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "annotation_rounds"
)
REPORT_DIR = PROJECT_ROOT / "benchmarks" / "rair_rag" / "reports"
DEFAULT_BASE = ROUND_DIR / "round1_merged.csv"
DEFAULT_ANN_A = ROUND_DIR / "round1_annotator_A.csv"
DEFAULT_ANN_B = ROUND_DIR / "round1_annotator_B.csv"
DEFAULT_METRICS = REPORT_DIR / "agreement_metrics.json"
DEFAULT_OUT = ROUND_DIR / "adjudication_sheet.csv"

FIELDNAMES = [
    "id",
    "raw_input",
    "canonical_input",
    "template_perturbation_types",
    "template_positive_risks",
    "template_negated_risks",
    "template_operational_constraints",
    "template_primary_intent",
    "template_secondary_intents",
    "template_expected_route",
    "template_expected_protocol_id",
    "template_should_not_trigger",
    "template_risk_level",
    "screening_human_accept",
    "screening_human_notes",
    "disagreement_fields",
    "annotator_a_human_accept",
    "annotator_a_primary_intent",
    "annotator_a_secondary_intents",
    "annotator_a_negated_risks",
    "annotator_a_operational_constraints",
    "annotator_a_should_not_trigger",
    "annotator_a_notes",
    "annotator_b_human_accept",
    "annotator_b_primary_intent",
    "annotator_b_secondary_intents",
    "annotator_b_negated_risks",
    "annotator_b_operational_constraints",
    "annotator_b_should_not_trigger",
    "annotator_b_notes",
    "final_raw_input",
    "final_human_accept",
    "final_primary_intent",
    "final_secondary_intents",
    "final_negated_risks",
    "final_operational_constraints",
    "final_should_not_trigger",
    "final_expected_route",
    "final_expected_protocol_id",
    "final_risk_level",
    "final_notes",
    "adjudicator_notes",
    "adjudicator_id",
    "adjudication_decision",
]

COMPARISON_FIELDS = {
    "human_accept": "human_accept",
    "primary_intent": "annotator_primary_intent",
    "secondary_intents": "annotator_secondary_intents",
    "negated_risks": "annotator_negated_risks",
    "operational_constraints": "annotator_operational_constraints",
    "should_not_trigger": "annotator_should_not_trigger",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a RAIR-RAG adjudication sheet from disagreement ids."
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--ann-a", type=Path, default=DEFAULT_ANN_A)
    parser.add_argument("--ann-b", type=Path, default=DEFAULT_ANN_B)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    count = build_adjudication_sheet(
        base_path=args.base,
        ann_a_path=args.ann_a,
        ann_b_path=args.ann_b,
        metrics_path=args.metrics,
        out_path=args.out,
        overwrite=args.overwrite,
    )
    print(f"wrote {count} rows to {args.out}")


def build_adjudication_sheet(
    *,
    base_path: Path,
    ann_a_path: Path,
    ann_b_path: Path,
    metrics_path: Path,
    out_path: Path,
    overwrite: bool,
) -> int:
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"output already exists; pass --overwrite: {out_path}")

    base_rows = read_csv_indexed(base_path)
    ann_a_rows = read_csv_indexed(ann_a_path)
    ann_b_rows = read_csv_indexed(ann_b_path)
    disagreement_ids = read_disagreement_ids(metrics_path)
    if not disagreement_ids:
        raise ValueError(f"{metrics_path}: all_disagreement_ids is empty")

    output_rows: list[dict[str, str]] = []
    for item_id in disagreement_ids:
        require_id(base_rows, item_id, base_path)
        require_id(ann_a_rows, item_id, ann_a_path)
        require_id(ann_b_rows, item_id, ann_b_path)
        output_rows.append(
            build_row(
                item_id=item_id,
                base=base_rows[item_id],
                ann_a=ann_a_rows[item_id],
                ann_b=ann_b_rows[item_id],
            )
        )

    write_csv(out_path, output_rows)
    return len(output_rows)


def read_csv_indexed(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    output: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        item_id = clean(row.get("id", ""))
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


def require_id(rows: dict[str, dict[str, str]], item_id: str, path: Path) -> None:
    if item_id not in rows:
        raise ValueError(f"{path}: missing disagreement id {item_id}")


def build_row(
    *,
    item_id: str,
    base: dict[str, str],
    ann_a: dict[str, str],
    ann_b: dict[str, str],
) -> dict[str, str]:
    row = dict.fromkeys(FIELDNAMES, "")
    row.update(
        {
            "id": item_id,
            "raw_input": base.get("raw_input", ""),
            "canonical_input": base.get("canonical_input", ""),
            "template_perturbation_types": base.get("perturbation_types", ""),
            "template_positive_risks": base.get("positive_risks", ""),
            "template_negated_risks": base.get("negated_risks", ""),
            "template_operational_constraints": base.get(
                "operational_constraints", ""
            ),
            "template_primary_intent": base.get("primary_intent", ""),
            "template_secondary_intents": base.get("secondary_intents", ""),
            "template_expected_route": base.get("expected_route", ""),
            "template_expected_protocol_id": base.get("expected_protocol_id", ""),
            "template_should_not_trigger": base.get("should_not_trigger", ""),
            "template_risk_level": base.get("risk_level", ""),
            "screening_human_accept": base.get("human_accept", ""),
            "screening_human_notes": base.get("human_notes", ""),
            "disagreement_fields": "|".join(disagreement_fields(ann_a, ann_b)),
            "annotator_a_human_accept": ann_a.get("human_accept", ""),
            "annotator_a_primary_intent": ann_a.get("annotator_primary_intent", ""),
            "annotator_a_secondary_intents": ann_a.get(
                "annotator_secondary_intents", ""
            ),
            "annotator_a_negated_risks": ann_a.get("annotator_negated_risks", ""),
            "annotator_a_operational_constraints": ann_a.get(
                "annotator_operational_constraints", ""
            ),
            "annotator_a_should_not_trigger": ann_a.get(
                "annotator_should_not_trigger", ""
            ),
            "annotator_a_notes": ann_a.get("annotator_notes", ""),
            "annotator_b_human_accept": ann_b.get("human_accept", ""),
            "annotator_b_primary_intent": ann_b.get("annotator_primary_intent", ""),
            "annotator_b_secondary_intents": ann_b.get(
                "annotator_secondary_intents", ""
            ),
            "annotator_b_negated_risks": ann_b.get("annotator_negated_risks", ""),
            "annotator_b_operational_constraints": ann_b.get(
                "annotator_operational_constraints", ""
            ),
            "annotator_b_should_not_trigger": ann_b.get(
                "annotator_should_not_trigger", ""
            ),
            "annotator_b_notes": ann_b.get("annotator_notes", ""),
        }
    )
    return row


def disagreement_fields(
    ann_a: dict[str, str], ann_b: dict[str, str]
) -> list[str]:
    fields: list[str] = []
    for logical_name, column_name in COMPARISON_FIELDS.items():
        if ann_a.get(column_name, "") != ann_b.get(column_name, ""):
            fields.append(logical_name)
    return fields


def clean(value: Any) -> str:
    return (value or "").strip()


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
