from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.config import PROJECT_ROOT
from benchmarks.schema import load_cases

CANDIDATE_FIELDS = ("case_id", "query", "scenario", "source_type", "source_note")
ANNOTATOR_FIELDS = (
    "case_id",
    "annotator_id",
    "annotator_background",
    "query",
    "scenario",
    "risk_level",
    "expected_route",
    "expected_protocol_id",
    "expected_primary_intent",
    "expected_tags",
    "gold_chunk_ids",
    "unsafe_actions",
    "reference_reply",
    "notes",
)


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def export_candidates(
    input_path: str | Path,
    output_path: str | Path,
    source_type: str = "existing_seed",
) -> int:
    cases = load_cases(input_path)
    out = _resolve(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case.id,
                    "query": case.clean_query or case.query,
                    "scenario": case.expected_primary_intent or case.expected_route or "",
                    "source_type": source_type,
                    "source_note": "exported from existing benchmark seed",
                }
            )
    return len(cases)


def export_blank_annotator_sheet(
    input_path: str | Path,
    output_path: str | Path,
    annotator_id: str,
) -> int:
    cases = load_cases(input_path)
    out = _resolve(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATOR_FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case.id,
                    "annotator_id": annotator_id,
                    "annotator_background": "",
                    "query": case.clean_query or case.query,
                    "scenario": case.expected_primary_intent or case.expected_route or "",
                    "risk_level": "",
                    "expected_route": "",
                    "expected_protocol_id": "",
                    "expected_primary_intent": "",
                    "expected_tags": "",
                    "gold_chunk_ids": "",
                    "unsafe_actions": "",
                    "reference_reply": "",
                    "notes": "",
                }
            )
    return len(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export clean benchmark cases into annotation CSV templates."
    )
    parser.add_argument("--input", default="benchmarks/data/clean_dev.jsonl")
    parser.add_argument(
        "--candidates-out",
        default="benchmarks/data/annotation/clean_candidates_seed.csv",
    )
    parser.add_argument("--annotator-a-out")
    parser.add_argument("--annotator-b-out")
    args = parser.parse_args(argv)

    num_cases = export_candidates(args.input, args.candidates_out)
    if args.annotator_a_out:
        export_blank_annotator_sheet(args.input, args.annotator_a_out, "A")
    if args.annotator_b_out:
        export_blank_annotator_sheet(args.input, args.annotator_b_out, "B")
    print(f"exported {num_cases} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
