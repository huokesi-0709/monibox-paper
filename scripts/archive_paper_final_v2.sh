#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

python - <<'PY'
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path.cwd()
FINAL = ROOT / "build" / "eval" / "final_v2"
DATA = ROOT / "benchmarks" / "data_v2"
ARCHIVE = ROOT / "artifacts" / "paper_final_v2"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def ensure_dirs() -> None:
    for name in [
        "",
        "dataset",
        "summaries",
        "tables",
        "statistics",
        "cases",
        "human_review",
        "manifests",
        "validation",
    ]:
        (ARCHIVE / name).mkdir(parents=True, exist_ok=True)


def copy_one(src: Path, dst: Path, copied: list[dict], missing: list[str]) -> None:
    if not src.exists():
        missing.append(rel(src))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append(
        {
            "source": rel(src),
            "archive_path": rel(dst),
            "bytes": dst.stat().st_size,
            "sha256": sha256_file(dst),
        }
    )


def copy_many(paths: list[Path], dst_dir: Path, copied: list[dict], missing: list[str]) -> None:
    for src in paths:
        copy_one(src, dst_dir / src.name, copied, missing)


def copy_preserve(base: Path, paths: list[Path], dst_dir: Path, copied: list[dict], missing: list[str]) -> None:
    for src in paths:
        copy_one(src, dst_dir / src.relative_to(base), copied, missing)


def prediction_record(path: Path) -> dict:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "samples": count_jsonl(path),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else "",
    }


def write_readme() -> None:
    text = """# HSC-RAG paper final_v2 experiment package

This directory contains the reproducible experiment package for the HSC-RAG paper.

本目录包含 HSC-RAG 论文 final_v2 实验包。论文主结果来自 HSC-DisasterBench-v2 的全量 test 评测。数字复核材料仅用于辅助误差分析，不作为真实应急医学或救援专家评估。

## Contents

- `dataset/`: dataset card, audit report, and split manifest.
- `summaries/`: final_v2 summary JSON files for clean, robust, ablation, and DE multiseed runs.
- `tables/`: paper-ready markdown and CSV tables.
- `statistics/`: exported metrics, bootstrap CI, warnings, and statistics reports.
- `cases/`: selected real prediction cases for error analysis.
- `human_review/`: balanced digital review sample, A/B/C labels, and disagreement report.
- `manifests/`: final run and paper evidence manifests.
- `validation/`: final_v2 validation reports.
- `predictions_manifest.md`: prediction file paths, sample counts, and hashes. Prediction JSONL files are kept in `build/eval/final_v2/` and are not duplicated here.

## Rule

The main paper conclusions should be based on full test automatic metrics. Digital review artifacts are auxiliary error-analysis evidence only.
"""
    (ARCHIVE / "README.md").write_text(text, encoding="utf-8")


def write_predictions_manifest() -> None:
    prediction_files = []
    for suite in ["clean", "robust", "ablation"]:
        prediction_files.extend(sorted((FINAL / suite).glob("*_predictions.jsonl")))

    lines = [
        "# final_v2 predictions manifest",
        "",
        "Large prediction JSONL files are not duplicated in `artifacts/paper_final_v2/`.",
        "They remain under `build/eval/final_v2/` and can be regenerated with the final_v2 scripts.",
        "",
        "| Suite | File | Samples | Bytes | SHA256 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for path in prediction_files:
        record = prediction_record(path)
        suite = path.parent.name
        lines.append(
            f"| {suite} | `{record['path']}` | {record['samples']} | {record['bytes']} | `{record['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Regeneration",
            "",
            "Use Git Bash on this Windows workspace:",
            "",
            "```powershell",
            "& \"D:\\app\\Git\\Git\\bin\\bash.exe\" scripts/run_final_v2_all.sh",
            "```",
        ]
    )
    (ARCHIVE / "predictions_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_archive_manifest(copied: list[dict], missing: list[str]) -> None:
    grouped: dict[str, list[str]] = {}
    for path in sorted(ARCHIVE.rglob("*")):
        if path.is_file():
            parent = path.parent.relative_to(ARCHIVE).as_posix()
            grouped.setdefault(parent if parent != "." else ".", []).append(path.name)

    lines = [
        "# paper_final_v2 archive manifest",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Archive dir: `{rel(ARCHIVE)}`",
        f"- Copied file count: {len(copied)}",
        f"- Missing item count: {len(missing)}",
        "",
        "## Directory contents",
        "",
    ]
    for group, names in sorted(grouped.items()):
        lines.append(f"### {group}")
        lines.append("")
        for name in sorted(names):
            lines.append(f"- `{name}`")
        lines.append("")

    lines.extend(["## Missing items", ""])
    lines.extend([f"- `{item}`" for item in missing] or ["- None"])
    lines.extend(["", "## Copied files", ""])
    for item in copied:
        lines.append(
            f"- `{item['archive_path']}` from `{item['source']}` ({item['bytes']} bytes, sha256 `{item['sha256']}`)"
        )
    (ARCHIVE / "ARCHIVE_MANIFEST.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    json_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_dir": rel(ARCHIVE),
        "copied": copied,
        "missing": missing,
        "directories": grouped,
    }
    (ARCHIVE / "ARCHIVE_MANIFEST.json").write_text(
        json.dumps(json_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ensure_dirs()
    copied: list[dict] = []
    missing: list[str] = []

    copy_many(
        [
            DATA / "dataset_card.md",
            DATA / "dataset_audit.md",
            DATA / "split_manifest.json",
        ],
        ARCHIVE / "dataset",
        copied,
        missing,
    )
    copy_many(sorted((FINAL / "tables").glob("*.md")), ARCHIVE / "tables", copied, missing)
    copy_many(sorted((FINAL / "tables").glob("*.csv")), ARCHIVE / "tables", copied, missing)
    copy_many(sorted((FINAL / "statistics").glob("*.md")), ARCHIVE / "statistics", copied, missing)
    copy_many(sorted((FINAL / "statistics").glob("*.csv")), ARCHIVE / "statistics", copied, missing)
    copy_many(sorted((FINAL / "statistics").glob("*.json")), ARCHIVE / "statistics", copied, missing)
    copy_many(
        [
            FINAL / "cases" / "selected_cases.md",
            FINAL / "cases" / "selected_cases.json",
        ],
        ARCHIVE / "cases",
        copied,
        missing,
    )
    copy_many(
        [
            FINAL / "human_review" / "README.md",
            FINAL / "human_review" / "review_sample_balanced_300.jsonl",
            FINAL / "human_review" / "annotator_A_labels_balanced_300.jsonl",
            FINAL / "human_review" / "annotator_B_labels_balanced_300.jsonl",
            FINAL / "human_review" / "final_labels_C_balanced_300.jsonl",
            FINAL / "human_review" / "disagreement_report_balanced_300.md",
            FINAL / "human_review" / "disagreement_report_balanced_300.json",
            FINAL / "human_review" / "digital_review_summary.csv",
        ],
        ARCHIVE / "human_review",
        copied,
        missing,
    )
    copy_many(
        [
            FINAL / "paper_evidence_manifest.json",
            FINAL / "final_run_manifest.json",
        ],
        ARCHIVE / "manifests",
        copied,
        missing,
    )
    copy_many(
        [
            FINAL / "final_v2_validation_report.md",
            FINAL / "final_v2_validation_report.json",
        ],
        ARCHIVE / "validation",
        copied,
        missing,
    )
    copy_many(sorted((FINAL / "clean").glob("*_summary.json")), ARCHIVE / "summaries" / "clean", copied, missing)
    copy_many(sorted((FINAL / "robust").glob("*_summary.json")), ARCHIVE / "summaries" / "robust", copied, missing)
    copy_many(sorted((FINAL / "ablation").glob("*_summary.json")), ARCHIVE / "summaries" / "ablation", copied, missing)
    copy_preserve(
        FINAL / "de_multiseed",
        sorted((FINAL / "de_multiseed").glob("seed_*/*.json")),
        ARCHIVE / "summaries" / "de_multiseed",
        copied,
        missing,
    )
    copy_many(sorted((FINAL / "de_multiseed").glob("*.csv")), ARCHIVE / "summaries" / "de_multiseed", copied, missing)
    copy_many(sorted((FINAL / "de_multiseed").glob("*.md")), ARCHIVE / "summaries" / "de_multiseed", copied, missing)

    write_readme()
    write_predictions_manifest()
    write_archive_manifest(copied, missing)
    print(json.dumps({"archive": rel(ARCHIVE), "copied": len(copied), "missing": missing}, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


raise SystemExit(main())
PY
