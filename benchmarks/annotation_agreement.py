from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

CATEGORICAL_FIELDS = (
    "risk_level",
    "expected_route",
    "expected_protocol_id",
    "expected_primary_intent",
)
MULTILABEL_FIELDS = ("expected_tags", "gold_chunk_ids", "unsafe_actions")


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _load_rows(path: str | Path) -> dict[str, dict[str, str]]:
    resolved = _resolve(path)
    with resolved.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by_id: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        case_id = (row.get("case_id") or "").strip()
        if not case_id:
            msg = f"{resolved}: row {index} is missing case_id"
            raise ValueError(msg)
        if case_id in by_id:
            msg = f"{resolved}: duplicate case_id {case_id!r}"
            raise ValueError(msg)
        by_id[case_id] = {key: (value or "").strip() for key, value in row.items()}
    return by_id


def cohen_kappa(left: list[str], right: list[str]) -> float:
    if len(left) != len(right):
        msg = "left and right label lists must have the same length"
        raise ValueError(msg)
    if not left:
        return 0.0

    total = len(left)
    observed = sum(1 for a, b in zip(left, right, strict=True) if a == b) / total
    left_counts = Counter(left)
    right_counts = Counter(right)
    labels = set(left_counts) | set(right_counts)
    expected = sum((left_counts[label] / total) * (right_counts[label] / total) for label in labels)

    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def _split_multilabel(value: str) -> set[str]:
    if not value.strip():
        return set()
    normalized = value.replace("|", ";").replace("；", ";")
    return {item.strip() for item in normalized.split(";") if item.strip()}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def compute_agreement(
    annotator_a_path: str | Path,
    annotator_b_path: str | Path,
) -> dict[str, Any]:
    rows_a = _load_rows(annotator_a_path)
    rows_b = _load_rows(annotator_b_path)
    ids_a = set(rows_a)
    ids_b = set(rows_b)
    common_ids = sorted(ids_a & ids_b)

    if not common_ids:
        msg = "no overlapping case_id values between annotator files"
        raise ValueError(msg)

    categorical: dict[str, dict[str, float | int]] = {}
    for field in CATEGORICAL_FIELDS:
        left = [rows_a[case_id].get(field, "") for case_id in common_ids]
        right = [rows_b[case_id].get(field, "") for case_id in common_ids]
        agreement = sum(1 for a, b in zip(left, right, strict=True) if a == b) / len(common_ids)
        categorical[field] = {
            "cohen_kappa": cohen_kappa(left, right),
            "raw_agreement": agreement,
            "num_cases": len(common_ids),
        }

    multilabel: dict[str, dict[str, float | int]] = {}
    for field in MULTILABEL_FIELDS:
        scores = [
            _jaccard(
                _split_multilabel(rows_a[case_id].get(field, "")),
                _split_multilabel(rows_b[case_id].get(field, "")),
            )
            for case_id in common_ids
        ]
        multilabel[field] = {
            "mean_jaccard": sum(scores) / len(scores),
            "num_cases": len(scores),
        }

    return {
        "num_common_cases": len(common_ids),
        "missing_from_annotator_a": sorted(ids_b - ids_a),
        "missing_from_annotator_b": sorted(ids_a - ids_b),
        "categorical_fields": categorical,
        "multilabel_fields": multilabel,
        "notes": [
            "Cohen's kappa is reported for single-label categorical fields.",
            "Multi-label fields are reported with mean Jaccard agreement; adjudicate disagreements manually before final labels.",
        ],
    }


def _write_csv(path: str | Path, report: dict[str, Any]) -> None:
    resolved = _resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["field", "metric", "value", "num_cases"]
        )
        writer.writeheader()
        for field, payload in report["categorical_fields"].items():
            writer.writerow(
                {
                    "field": field,
                    "metric": "cohen_kappa",
                    "value": f"{payload['cohen_kappa']:.6f}",
                    "num_cases": payload["num_cases"],
                }
            )
            writer.writerow(
                {
                    "field": field,
                    "metric": "raw_agreement",
                    "value": f"{payload['raw_agreement']:.6f}",
                    "num_cases": payload["num_cases"],
                }
            )
        for field, payload in report["multilabel_fields"].items():
            writer.writerow(
                {
                    "field": field,
                    "metric": "mean_jaccard",
                    "value": f"{payload['mean_jaccard']:.6f}",
                    "num_cases": payload["num_cases"],
                }
            )


def _write_json(path: str | Path, report: dict[str, Any]) -> None:
    resolved = _resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute inter-annotator agreement for MoniBox benchmark labels."
    )
    parser.add_argument("--annotator-a", required=True)
    parser.add_argument("--annotator-b", required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-csv")
    args = parser.parse_args(argv)

    report = compute_agreement(args.annotator_a, args.annotator_b)
    if args.out_json:
        _write_json(args.out_json, report)
    if args.out_csv:
        _write_csv(args.out_csv, report)
    if not args.out_json and not args.out_csv:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
