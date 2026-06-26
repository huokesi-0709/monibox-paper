from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from experiments.final_v2_utils import (
    ABLATIONS,
    DATA_FILES,
    DATA_V2_DIR,
    DE_SEEDS,
    FINAL_V2_DIR,
    FINAL_V2_SCRIPTS,
    MAIN_METHODS,
    count_jsonl,
    final_v2_artifacts,
    read_json,
    sha256_file,
    write_json,
)


def _file_record(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists else "",
        "bytes": path.stat().st_size if exists else 0,
    }


def _script_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for script in FINAL_V2_SCRIPTS:
        path = Path(script)
        records[script] = _file_record(path)
    python_modules = (
        "benchmarks/generate_dataset_v2.py",
        "benchmarks/audit_dataset_v2.py",
        "experiments/export_final_v2_statistics.py",
        "experiments/export_final_v2_tables.py",
        "experiments/export_final_v2_cases.py",
        "experiments/export_final_v2_manifest.py",
    )
    for module in python_modules:
        path = Path(module)
        records[module] = _file_record(path)
    return records


def _artifact_status(artifacts: dict[str, Any]) -> dict[str, Any]:
    status = json.loads(json.dumps(artifacts))
    for group in ("clean", "robust", "ablation"):
        for name, paths in status[group].items():
            prediction = Path(paths["prediction_path"])
            summary = Path(paths["summary_path"])
            paths["prediction_exists"] = prediction.exists()
            paths["summary_exists"] = summary.exists()
            paths["prediction_rows"] = count_jsonl(prediction)
            paths["summary"] = read_json(summary)
    for seed_name, paths in status["de_multiseed"].items():
        for key in ("policy_path", "metrics_path", "curve_path", "trials_path"):
            path = Path(paths[key])
            paths[f"{key}_exists"] = path.exists()
            paths[f"{key}_sha256"] = sha256_file(path) if path.exists() else ""
    return status


def export_manifest() -> dict[str, Any]:
    artifacts = _artifact_status(final_v2_artifacts())
    data_files = {
        filename: {
            **_file_record(DATA_V2_DIR / filename),
            "samples": count_jsonl(DATA_V2_DIR / filename),
        }
        for filename in DATA_FILES
    }
    manifest = {
        "dataset": "HSC-DisasterBench-v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_dir": str(FINAL_V2_DIR),
        "data_files": data_files,
        "scripts": _script_records(),
        "methods": {
            "main": list(MAIN_METHODS),
            "ablation": list(ABLATIONS),
            "de_multiseed": [f"seed_{seed}" for seed in DE_SEEDS],
        },
        "artifacts": artifacts,
        "outputs": {
            "statistics": str(FINAL_V2_DIR / "statistics" / "final_v2_statistics.json"),
            "tables": str(FINAL_V2_DIR / "tables"),
            "cases": str(FINAL_V2_DIR / "cases"),
            "manifest": str(FINAL_V2_DIR / "final_run_manifest.json"),
        },
    }
    write_json(FINAL_V2_DIR / "final_run_manifest.json", manifest)
    return manifest


def main() -> int:
    manifest = export_manifest()
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
