from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IN = (
    PROJECT_ROOT
    / "benchmarks"
    / "rair_rag"
    / "data"
    / "candidates"
    / "rair_candidates.jsonl"
)
DEFAULT_OUT = (
    PROJECT_ROOT
    / "benchmarks"
    / "rair_rag"
    / "data"
    / "annotation_rounds"
    / "round1_for_annotation.csv"
)

CSV_FIELDS = [
    "id",
    "raw_input",
    "canonical_input",
    "perturbation_types",
    "risk_mentions",
    "positive_risks",
    "negated_risks",
    "operational_constraints",
    "primary_intent",
    "secondary_intents",
    "expected_route",
    "expected_protocol_id",
    "should_not_trigger",
    "risk_level",
    "guideline_refs",
    "human_accept",
    "human_notes",
    "annotator_primary_intent",
    "annotator_negated_risks",
    "annotator_secondary_intents",
]

HUMAN_FIELDS = {
    "human_accept",
    "human_notes",
    "annotator_primary_intent",
    "annotator_negated_risks",
    "annotator_secondary_intents",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert RAIR-RAG candidate JSONL to annotation CSV."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    count = convert_jsonl_to_csv(args.input, args.out, overwrite=args.overwrite)
    print(f"wrote {count} rows to {args.out}")


def convert_jsonl_to_csv(input_path: Path, out_path: Path, *, overwrite: bool) -> int:
    if out_path.exists() and not overwrite:
        raise FileExistsError(
            f"{out_path} already exists; pass --overwrite to replace it"
        )
    rows = load_jsonl(input_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(to_csv_row(row))
    return len(rows)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError(f"{path}:line {lineno}: expected JSON object")
        rows.append(data)
    return rows


def to_csv_row(data: dict[str, Any]) -> dict[str, str]:
    row: dict[str, str] = {}
    for field_name in CSV_FIELDS:
        if field_name in HUMAN_FIELDS:
            row[field_name] = ""
        else:
            row[field_name] = stringify_cell(data.get(field_name))
    return row


def stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(stringify_list_item(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def stringify_list_item(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


if __name__ == "__main__":
    main()
