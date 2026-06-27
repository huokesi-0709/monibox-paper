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
    read_csv_rows,
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


def _table_records() -> dict[str, dict[str, Any]]:
    table_names = (
        "table_dataset_distribution",
        "table11_overall_performance",
        "table12_perturbation_results",
        "table13_ablation_results",
        "table14_de_effect",
        "table15_safety_metrics",
        "table16_efficiency",
        "table17_bootstrap_ci",
        "table18_digital_review",
        "paper_tables_all",
    )
    records: dict[str, dict[str, Any]] = {}
    for name in table_names:
        md_path = FINAL_V2_DIR / "tables" / f"{name}.md"
        csv_path = FINAL_V2_DIR / "tables" / f"{name}.csv"
        if name == "paper_tables_all":
            csv_path = FINAL_V2_DIR / "tables" / "paper_tables_all.csv"
        records[name] = {
            "markdown": _file_record(md_path),
            "csv": _file_record(csv_path),
        }
    return records


def _case_records() -> dict[str, dict[str, Any]]:
    return {
        "selected_cases_md": _file_record(FINAL_V2_DIR / "cases" / "selected_cases.md"),
        "selected_cases_json": _file_record(FINAL_V2_DIR / "cases" / "selected_cases.json"),
    }


def _warnings() -> list[str]:
    warnings: list[str] = []
    stats_warning_path = FINAL_V2_DIR / "statistics" / "statistics_warnings.md"
    if stats_warning_path.exists():
        text = stats_warning_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("- ") and line.strip() != "- None":
                warnings.append(line[2:])
    cases_json = read_json(FINAL_V2_DIR / "cases" / "selected_cases.json")
    for warning in cases_json.get("warnings", []) if isinstance(cases_json.get("warnings"), list) else []:
        warnings.append(f"cases: {warning}")
    if not (FINAL_V2_DIR / "human_review" / "digital_review_summary.csv").exists():
        warnings.append("digital_review: missing final_v2 human_review/digital_review_summary.csv; table18 is a placeholder")
    return warnings


def _write_readme(manifest: dict[str, Any]) -> str:
    path = FINAL_V2_DIR / "README.md"
    lines = [
        "# final_v2 Evidence Package",
        "",
        f"- Generated at: {manifest['generated_at']}",
        f"- Dataset: {manifest['dataset']}",
        f"- Eval dir: `{manifest['eval_dir']}`",
        f"- Warnings: {len(manifest.get('warnings') or [])}",
        "",
        "## Key Files",
        "",
        "- `statistics/final_metrics_by_method.csv`",
        "- `statistics/bootstrap_ci.csv`",
        "- `tables/paper_tables_all.md`",
        "- `cases/selected_cases.md`",
        "- `paper_evidence_manifest.json`",
        "",
        "## Rule",
        "",
        "All paper chapter 4 numbers should be copied from this directory only.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def export_manifest() -> dict[str, Any]:
    artifacts = _artifact_status(final_v2_artifacts())
    data_files = {
        filename: {
            **_file_record(DATA_V2_DIR / filename),
            "samples": count_jsonl(DATA_V2_DIR / filename),
        }
        for filename in DATA_FILES
    }
    warnings = _warnings()
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
        "tables": _table_records(),
        "cases": _case_records(),
        "digital_review": {
            "summary_csv": _file_record(FINAL_V2_DIR / "human_review" / "digital_review_summary.csv"),
            "balanced_report_json": _file_record(FINAL_V2_DIR / "human_review" / "disagreement_report_balanced_300.json"),
            "balanced_report_md": _file_record(FINAL_V2_DIR / "human_review" / "disagreement_report_balanced_300.md"),
            "table18_csv": _file_record(FINAL_V2_DIR / "tables" / "table18_digital_review.csv"),
            "table18_md": _file_record(FINAL_V2_DIR / "tables" / "table18_digital_review.md"),
        },
        "warnings": warnings,
        "outputs": {
            "statistics": str(FINAL_V2_DIR / "statistics" / "final_v2_statistics.json"),
            "tables": str(FINAL_V2_DIR / "tables"),
            "cases": str(FINAL_V2_DIR / "cases"),
            "manifest": str(FINAL_V2_DIR / "final_run_manifest.json"),
            "paper_evidence_manifest": str(FINAL_V2_DIR / "paper_evidence_manifest.json"),
            "readme": str(FINAL_V2_DIR / "README.md"),
        },
    }
    write_json(FINAL_V2_DIR / "final_run_manifest.json", manifest)
    write_json(FINAL_V2_DIR / "paper_evidence_manifest.json", manifest)
    manifest["outputs"]["readme"] = _write_readme(manifest)
    write_json(FINAL_V2_DIR / "final_run_manifest.json", manifest)
    write_json(FINAL_V2_DIR / "paper_evidence_manifest.json", manifest)
    return manifest


def main() -> int:
    manifest = export_manifest()
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
