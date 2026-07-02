from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.baselines.bert_multilabel_dataset import LABELS, labels_from_payload

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "dev" / "rair_dev.jsonl"
DEFAULT_TEST = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "bert_multilabel"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a BERT-only train/validation split from the existing dev pool "
            "while keeping the held-out test set untouched."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--test-data", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-train-cases", type=int, default=100)
    args = parser.parse_args()

    summary = prepare_bert_multilabel_split(
        input_path=args.input,
        test_path=args.test_data,
        out_dir=args.out_dir,
        train_ratio=args.train_ratio,
        seed=args.seed,
        min_train_cases=args.min_train_cases,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def prepare_bert_multilabel_split(
    *,
    input_path: Path,
    test_path: Path,
    out_dir: Path,
    train_ratio: float = 0.8,
    seed: int = 42,
    min_train_cases: int = 100,
) -> dict[str, Any]:
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1")
    rows = read_jsonl(input_path)
    test_rows = read_jsonl(test_path) if test_path.exists() else []
    test_case_ids = {str(row.get("id") or "") for row in test_rows}
    test_canonical_ids = {str(row.get("canonical_id") or "") for row in test_rows}
    leaked = [
        str(row.get("id") or row.get("canonical_id") or "<missing-id>")
        for row in rows
        if str(row.get("id") or "") in test_case_ids
        or str(row.get("canonical_id") or "") in test_canonical_ids
    ]
    if leaked:
        sample = ", ".join(leaked[:10])
        raise ValueError(
            "input overlaps with held-out test data by id or canonical_id; "
            f"examples: {sample}"
        )

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        canonical_id = str(row.get("canonical_id") or row.get("id") or "")
        if not canonical_id:
            raise ValueError("all rows must have id or canonical_id")
        groups.setdefault(canonical_id, []).append(row)

    canonical_ids = sorted(groups)
    rng = random.Random(seed)
    rng.shuffle(canonical_ids)
    train_ids, validation_ids = split_groups(canonical_ids, groups, train_ratio)
    train_rows = flatten_groups(train_ids, groups)
    validation_rows = flatten_groups(validation_ids, groups)
    if len(train_rows) < min_train_cases:
        raise ValueError(
            f"prepared training split has only {len(train_rows)} cases; "
            f"minimum required is {min_train_cases}"
        )
    if not validation_rows:
        raise ValueError("prepared validation split is empty")

    train_path = out_dir / "rair_train.jsonl"
    validation_path = out_dir / "rair_validation.jsonl"
    manifest_path = out_dir / "bert_split_manifest.json"
    write_jsonl(train_path, train_rows)
    write_jsonl(validation_path, validation_rows)
    manifest = {
        "input": str(input_path),
        "test_data": str(test_path),
        "train": str(train_path),
        "validation": str(validation_path),
        "seed": seed,
        "train_ratio": train_ratio,
        "leakage_rule": "held-out test ids and canonical_ids are excluded",
        "num_input_cases": len(rows),
        "num_train_cases": len(train_rows),
        "num_validation_cases": len(validation_rows),
        "num_train_canonical_ids": len(train_ids),
        "num_validation_canonical_ids": len(validation_ids),
        "label_space": list(LABELS),
        "train_label_distribution": label_distribution(train_rows),
        "validation_label_distribution": label_distribution(validation_rows),
    }
    write_json(manifest_path, manifest)
    return manifest


def split_groups(
    canonical_ids: list[str],
    groups: dict[str, list[dict[str, Any]]],
    train_ratio: float,
) -> tuple[list[str], list[str]]:
    target_train_cases = round(sum(len(groups[item]) for item in canonical_ids) * train_ratio)
    train_ids: list[str] = []
    validation_ids: list[str] = []
    train_count = 0
    for canonical_id in canonical_ids:
        group_size = len(groups[canonical_id])
        if train_count < target_train_cases:
            train_ids.append(canonical_id)
            train_count += group_size
        else:
            validation_ids.append(canonical_id)
    if not validation_ids and train_ids:
        validation_ids.append(train_ids.pop())
    return train_ids, validation_ids


def flatten_groups(
    canonical_ids: list[str], groups: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for canonical_id in canonical_ids:
        rows.extend(groups[canonical_id])
    return rows


def label_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        labels = labels_from_payload(row)
        if not labels:
            counter["<none>"] += 1
        for label in labels:
            counter[label] += 1
    return dict(sorted(counter.items()))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:line {lineno}: expected JSON object")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
