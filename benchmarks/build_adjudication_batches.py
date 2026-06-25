from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.config import PROJECT_ROOT

OUTPUT_FIELDS = (
    "case_id",
    "query",
    "scenario",
    "a_risk_level",
    "b_risk_level",
    "a_expected_route",
    "b_expected_route",
    "a_expected_protocol_id",
    "b_expected_protocol_id",
    "a_expected_primary_intent",
    "b_expected_primary_intent",
    "a_expected_tags",
    "b_expected_tags",
    "a_gold_chunk_ids",
    "b_gold_chunk_ids",
    "a_unsafe_actions",
    "b_unsafe_actions",
    "a_reference_reply",
    "b_reference_reply",
)


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _load(path: str | Path) -> dict[str, dict[str, str]]:
    with _resolve(path).open("r", encoding="utf-8-sig", newline="") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def build_adjudication_batches(
    annotator_a_path: str | Path,
    annotator_b_path: str | Path,
    output_dir: str | Path,
    batch_size: int = 50,
) -> int:
    if batch_size <= 0:
        msg = "batch_size must be positive"
        raise ValueError(msg)
    a_rows = _load(annotator_a_path)
    b_rows = _load(annotator_b_path)
    ids = sorted(set(a_rows) & set(b_rows))
    missing = (set(a_rows) ^ set(b_rows))
    if missing:
        msg = f"A/B case_id mismatch: {sorted(missing)[:10]}"
        raise ValueError(msg)

    out_dir = _resolve(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for start in range(0, len(ids), batch_size):
        count += 1
        out = out_dir / f"adjudication_batch_{count:02d}.csv"
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            for case_id in ids[start : start + batch_size]:
                a = a_rows[case_id]
                b = b_rows[case_id]
                writer.writerow(
                    {
                        "case_id": case_id,
                        "query": a.get("query", ""),
                        "scenario": a.get("scenario", ""),
                        "a_risk_level": a.get("risk_level", ""),
                        "b_risk_level": b.get("risk_level", ""),
                        "a_expected_route": a.get("expected_route", ""),
                        "b_expected_route": b.get("expected_route", ""),
                        "a_expected_protocol_id": a.get("expected_protocol_id", ""),
                        "b_expected_protocol_id": b.get("expected_protocol_id", ""),
                        "a_expected_primary_intent": a.get("expected_primary_intent", ""),
                        "b_expected_primary_intent": b.get("expected_primary_intent", ""),
                        "a_expected_tags": a.get("expected_tags", ""),
                        "b_expected_tags": b.get("expected_tags", ""),
                        "a_gold_chunk_ids": a.get("gold_chunk_ids", ""),
                        "b_gold_chunk_ids": b.get("gold_chunk_ids", ""),
                        "a_unsafe_actions": a.get("unsafe_actions", ""),
                        "b_unsafe_actions": b.get("unsafe_actions", ""),
                        "a_reference_reply": a.get("reference_reply", ""),
                        "b_reference_reply": b.get("reference_reply", ""),
                    }
                )
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build adjudication input batches.")
    parser.add_argument("--annotator-a", required=True)
    parser.add_argument("--annotator-b", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args(argv)

    count = build_adjudication_batches(
        args.annotator_a, args.annotator_b, args.output_dir, args.batch_size
    )
    print(f"wrote {count} adjudication batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
