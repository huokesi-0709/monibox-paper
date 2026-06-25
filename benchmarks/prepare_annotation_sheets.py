from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.config import PROJECT_ROOT
from benchmarks.export_annotation_candidates import ANNOTATOR_FIELDS


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def prepare_sheet(
    candidates_path: str | Path,
    output_path: str | Path,
    annotator_id: str,
) -> int:
    candidates = _resolve(candidates_path)
    with candidates.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    out = _resolve(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATOR_FIELDS)
        writer.writeheader()
        for index, row in enumerate(rows, start=2):
            case_id = (row.get("case_id") or "").strip()
            query = (row.get("query") or "").strip()
            if not case_id or not query:
                msg = f"{candidates}: row {index} must contain case_id and query"
                raise ValueError(msg)
            writer.writerow(
                {
                    "case_id": case_id,
                    "annotator_id": annotator_id,
                    "annotator_background": "",
                    "query": query,
                    "scenario": (row.get("scenario") or "").strip(),
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
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create blank annotator sheets from clean candidate CSV."
    )
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--annotator-a-out", required=True)
    parser.add_argument("--annotator-b-out", required=True)
    args = parser.parse_args(argv)

    count_a = prepare_sheet(args.candidates, args.annotator_a_out, "A")
    count_b = prepare_sheet(args.candidates, args.annotator_b_out, "B")
    if count_a != count_b:
        msg = "annotator sheet row counts differ unexpectedly"
        raise RuntimeError(msg)
    print(f"prepared {count_a} cases for annotators A and B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
