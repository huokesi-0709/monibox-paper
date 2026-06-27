from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


FINAL_V2_DIR = PROJECT_ROOT / "build" / "eval" / "final_v2"
DATA_V2_DIR = PROJECT_ROOT / "benchmarks" / "data_v2"

MAIN_METHODS = ("vanilla-rag", "rag-guard", "hsc-rag-manual", "hsc-rag-de")
ABLATIONS = (
    "without_input_normalization",
    "without_multi_intent",
    "without_negation",
    "without_protocol_gate",
    "without_safety_rerank",
    "without_low_evidence",
    "without_guard",
    "without_de_optimization",
)
DE_SEEDS = (7, 21, 42, 2024, 2026)
DATA_FILES = (
    "clean_dev.jsonl",
    "robustness_dev.jsonl",
    "clean_test.jsonl",
    "robustness_test.jsonl",
)
FINAL_V2_SCRIPTS = (
    "scripts/run_final_v2_clean_eval.sh",
    "scripts/run_final_v2_robust_eval.sh",
    "scripts/run_final_v2_ablation.sh",
    "scripts/run_final_v2_de_multiseed.sh",
    "scripts/run_final_v2_all.sh",
)


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def sha256_file(path: str | Path) -> str:
    resolved = resolve(path)
    digest = hashlib.sha256()
    with resolved.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_jsonl(path: str | Path) -> int:
    resolved = resolve(path)
    if not resolved.exists():
        return 0
    with resolved.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = resolve(path)
    if not resolved.exists():
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    resolved = resolve(path)
    if not resolved.exists():
        return []
    with resolved.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    resolved = resolve(path)
    if not resolved.exists():
        return []
    rows: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if text:
                data = json.loads(text)
                if isinstance(data, dict):
                    rows.append(data)
    return rows


def write_json(path: str | Path, obj: dict[str, Any]) -> None:
    resolved = resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    resolved = resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown_table(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    resolved = resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| " + " | ".join(fieldnames) + " |",
        "| " + " | ".join("---" for _ in fieldnames) + " |",
    ]
    for row in rows:
        cells = [str(row.get(field, "")).replace("|", "\\|") for field in fieldnames]
        lines.append("| " + " | ".join(cells) + " |")
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prediction_summary_pair(directory: str, name: str) -> dict[str, str]:
    base = FINAL_V2_DIR / directory
    return {
        "prediction_path": str(base / f"{name}_predictions.jsonl"),
        "summary_path": str(base / f"{name}_summary.json"),
    }


def load_summary(directory: str, name: str) -> dict[str, Any]:
    path = FINAL_V2_DIR / directory / f"{name}_summary.json"
    row = read_json(path)
    if row:
        row["_source"] = str(path)
    return row


def final_v2_artifacts() -> dict[str, Any]:
    return {
        "clean": {
            method: prediction_summary_pair("clean", method) for method in MAIN_METHODS
        },
        "robust": {
            method: prediction_summary_pair("robust", method) for method in MAIN_METHODS
        },
        "ablation": {
            ablation: prediction_summary_pair("ablation", ablation)
            for ablation in ABLATIONS
        },
        "de_multiseed": {
            f"seed_{seed}": {
                "policy_path": str(
                    FINAL_V2_DIR
                    / "de_multiseed"
                    / f"seed_{seed}"
                    / f"policy_de_seed_{seed}.json"
                ),
                "metrics_path": str(
                    FINAL_V2_DIR
                    / "de_multiseed"
                    / f"seed_{seed}"
                    / "de_best_metrics.json"
                ),
                "curve_path": str(
                    FINAL_V2_DIR / "de_multiseed" / f"seed_{seed}" / "de_curve.csv"
                ),
                "trials_path": str(
                    FINAL_V2_DIR / "de_multiseed" / f"seed_{seed}" / "de_trials.csv"
                ),
            }
            for seed in DE_SEEDS
        },
    }
