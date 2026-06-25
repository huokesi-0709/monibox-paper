from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from benchmarks.schema import BenchmarkCase

LIST_SEPARATORS = (";", "；", "|")


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value
    for sep in LIST_SEPARATORS[1:]:
        normalized = normalized.replace(sep, LIST_SEPARATORS[0])
    return [item.strip() for item in normalized.split(LIST_SEPARATORS[0]) if item.strip()]


def _load_final_labels(path: str | Path) -> list[dict[str, str]]:
    resolved = _resolve(path)
    with resolved.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        msg = f"{resolved} contains no rows"
        raise ValueError(msg)
    return rows


def _to_case(row: dict[str, str]) -> BenchmarkCase:
    case_id = (row.get("case_id") or "").strip()
    query = (row.get("query") or "").strip()
    payload: dict[str, Any] = {
        "id": case_id,
        "query": query,
        "clean_id": None,
        "canonical_id": case_id,
        "clean_query": query,
        "perturbation_type": "clean",
        "risk_level": (row.get("risk_level") or "").strip(),
        "expected_route": (row.get("expected_route") or "").strip(),
        "expected_protocol_id": (row.get("expected_protocol_id") or "").strip(),
        "expected_primary_intent": (row.get("expected_primary_intent") or "").strip(),
        "expected_tags": _split_list(row.get("expected_tags")),
        "gold_chunk_ids": _split_list(row.get("gold_chunk_ids")),
        "unsafe_actions": _split_list(row.get("unsafe_actions")),
        "reference_reply": (row.get("reference_reply") or "").strip(),
    }
    return BenchmarkCase.from_dict(payload)


def _stratified_split(
    rows: list[dict[str, str]], dev_size: int
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if dev_size <= 0 or dev_size >= len(rows):
        msg = "dev_size must be positive and smaller than the number of rows"
        raise ValueError(msg)

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = row.get("scenario") or row.get("expected_primary_intent") or "unknown"
        groups[key].append(row)
    for group_rows in groups.values():
        group_rows.sort(key=lambda item: item["case_id"])

    total = len(rows)
    raw_targets = {
        key: len(group_rows) * dev_size / total for key, group_rows in groups.items()
    }
    targets = {key: int(value) for key, value in raw_targets.items()}
    remainder = dev_size - sum(targets.values())
    order = sorted(
        raw_targets,
        key=lambda key: (raw_targets[key] - targets[key], len(groups[key]), key),
        reverse=True,
    )
    for key in order[:remainder]:
        targets[key] += 1

    dev: list[dict[str, str]] = []
    test: list[dict[str, str]] = []
    for key in sorted(groups):
        group_rows = groups[key]
        target = targets[key]
        dev.extend(group_rows[:target])
        test.extend(group_rows[target:])
    dev.sort(key=lambda item: item["case_id"])
    test.sort(key=lambda item: item["case_id"])
    return dev, test


def write_cases(path: str | Path, cases: list[BenchmarkCase]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for case in cases:
            case.validate()
            f.write(json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True))
            f.write("\n")


def convert_final_labels(
    final_labels_path: str | Path,
    clean_dev_out: str | Path,
    clean_test_out: str | Path,
    dev_size: int = 150,
    stats_out: str | Path | None = None,
) -> dict[str, Any]:
    rows = _load_final_labels(final_labels_path)
    dev_rows, test_rows = _stratified_split(rows, dev_size=dev_size)
    dev_cases = [_to_case(row) for row in dev_rows]
    test_cases = [_to_case(row) for row in test_rows]
    write_cases(clean_dev_out, dev_cases)
    write_cases(clean_test_out, test_cases)

    stats: dict[str, Any] = {
        "clean_dev": len(dev_cases),
        "clean_test": len(test_cases),
        "dev_by_scenario": dict(Counter(row.get("scenario", "") for row in dev_rows)),
        "test_by_scenario": dict(Counter(row.get("scenario", "") for row in test_rows)),
        "dev_by_risk": dict(Counter(case.risk_level for case in dev_cases)),
        "test_by_risk": dict(Counter(case.risk_level for case in test_cases)),
    }
    if stats_out:
        out = _resolve(stats_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert adjudicated final labels into clean dev/test JSONL."
    )
    parser.add_argument(
        "--final-labels", default="benchmarks/data/annotation/final_labels.csv"
    )
    parser.add_argument("--clean-dev-out", default="benchmarks/data/clean_dev.jsonl")
    parser.add_argument("--clean-test-out", default="benchmarks/data/clean_test.jsonl")
    parser.add_argument("--dev-size", type=int, default=150)
    parser.add_argument("--stats-out", default="build/eval/annotation/split_stats.json")
    args = parser.parse_args(argv)

    stats = convert_final_labels(
        final_labels_path=args.final_labels,
        clean_dev_out=args.clean_dev_out,
        clean_test_out=args.clean_test_out,
        dev_size=args.dev_size,
        stats_out=args.stats_out,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
