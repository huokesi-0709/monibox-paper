from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

METHOD_DISPLAY_NAMES = {
    "keyword-baseline": "Keyword",
    "no-negation": "RAIR w/o Negation Modeling",
    "single-intent": "RAIR w/o Multi-Intent Routing",
    "risk-router": "RAIR",
    "bert-multilabel": "BERT-MultiLabel",
    "llm-zero-shot": "LLM-ZeroShot",
    "llm-few-shot": "LLM-FewShot",
    "risk-router-de": "Archived DE Calibration",
}

MAIN_METHODS = [
    "keyword-baseline",
    "bert-multilabel",
    "no-negation",
    "single-intent",
    "risk-router",
]

METHOD_ORDER = {method: index for index, method in enumerate(MAIN_METHODS)}

MAIN_SUMMARY_BY_METHOD = {
    method: f"rair_test_{method}_summary.json" for method in MAIN_METHODS
}

CANONICAL_DATASETS = [
    "rair_test",
    "rair_test_negation",
    "rair_test_multi_intent",
    "rair_test_multi_intent_negation",
]

CANONICAL_SUMMARY_NAMES = {
    f"{dataset}_{method}_summary.json"
    for dataset in CANONICAL_DATASETS
    for method in MAIN_METHODS
}

MAIN_FIELDS = [
    "Method",
    "Offline Deployable",
    "RouteAcc \u2191",
    "HRR \u2191",
    "PFTR \u2193",
    "NegRiskF1 \u2191",
    "SecondaryIntentF1 \u2191",
    "ConstraintF1 \u2191",
    "SuppressedProtocolF1 \u2191",
    "RiskCandidateF1 \u2191",
]

PERTURBATION_FIELDS = [
    "Method",
    "Offline Deployable",
    "Perturbation",
    "NumCases",
    "RouteAcc \u2191",
    "HRR \u2191",
    "PFTR \u2193",
    "NegRiskF1 \u2191",
    "SecondaryIntentF1 \u2191",
    "ConstraintF1 \u2191",
    "SuppressedProtocolF1 \u2191",
    "RiskCandidateF1 \u2191",
]

PERTURBATION_ORDER = [
    "clean_control",
    "negation_conflict",
    "multi_intent",
    "multi_intent_negation",
    "out_of_scope",
]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


def _read_predictions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _summaries_root(eval_dir: Path) -> list[Path]:
    return sorted(eval_dir.rglob("*_summary.json"))


def _method_display(method: str) -> str:
    return METHOD_DISPLAY_NAMES.get(method, method)


def _offline_deployable(method: str) -> str:
    return "No" if method in {"llm-zero-shot", "llm-few-shot"} else "Yes"


def _metric(summary: dict[str, Any], key: str, default: Any = 0.0) -> Any:
    metrics = summary.get("metrics")
    if isinstance(metrics, dict):
        if key in metrics:
            return metrics.get(key, default)
    return summary.get(key, default)


def _table_row(summary: dict[str, Any]) -> dict[str, Any]:
    method = str(summary.get("method") or "")
    return {
        "Method": _method_display(method),
        "_method": method,
        "Offline Deployable": _offline_deployable(method),
        "RouteAcc \u2191": _metric(summary, "RouteAcc"),
        "HRR \u2191": _metric(summary, "HRR"),
        "PFTR \u2193": _metric(summary, "PFTR"),
        "NegRiskF1 \u2191": _metric(summary, "NegRiskF1"),
        "SecondaryIntentF1 \u2191": _metric(summary, "SecondaryIntentF1"),
        "ConstraintF1 \u2191": _metric(summary, "ConstraintF1"),
        "SuppressedProtocolF1 \u2191": _metric(summary, "SuppressedProtocolF1"),
        "RiskCandidateF1 \u2191": _metric(summary, "RiskCandidateF1"),
        "_num_cases": summary.get("num_cases", _metric(summary, "num_cases", "")),
        "_summary": summary,
        "_summary_name": summary.get("_summary_name", ""),
        "_summary_path": summary.get("_summary_path", ""),
    }


def _suite_from_data(data: str) -> str:
    text = str(data).replace("\\", "/").lower()
    if "multi_intent" in text and "negation" in text:
        return "multi_intent_negation"
    if "multi_intent" in text:
        return "multi_intent"
    if "negation" in text:
        return "negation_conflict"
    if "out_of_scope" in text:
        return "out_of_scope"
    return "clean_control"


def _select_main_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for method in MAIN_METHODS:
        method_rows = [row for row in rows if row["_method"] == method]
        if not method_rows:
            continue
        preferred_name = MAIN_SUMMARY_BY_METHOD.get(method)
        preferred_rows = [
            row for row in method_rows if row.get("_summary_name") == preferred_name
        ]
        if preferred_rows:
            selected.append(preferred_rows[0])
            continue
        selected.append(
            max(
                method_rows,
                key=lambda row: (
                    int(row.get("_num_cases") or 0),
                    "manual" not in str(row.get("_summary_name") or ""),
                    "v2" not in str(row.get("_summary_name") or ""),
                ),
            )
        )
    return selected


def _select_ablation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row["_method"] in {"no-negation", "single-intent"}
        and row.get("_summary_name") in MAIN_SUMMARY_BY_METHOD.values()
    ]
    return sorted(
        selected,
        key=lambda row: (
            METHOD_ORDER.get(str(row["_method"]), 999),
            str(row["_method"]),
        ),
    )


def _perturbation_row(
    summary: dict[str, Any],
    perturbation: str,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics = metrics or {}
    method = str(summary.get("method") or "")
    return {
        "Method": _method_display(method),
        "Offline Deployable": _offline_deployable(method),
        "Perturbation": perturbation,
        "NumCases": metrics.get("num_cases", 0),
        "RouteAcc \u2191": metrics.get("RouteAcc", ""),
        "HRR \u2191": metrics.get("HRR", ""),
        "PFTR \u2193": metrics.get("PFTR", ""),
        "NegRiskF1 \u2191": metrics.get("NegRiskF1", ""),
        "SecondaryIntentF1 \u2191": metrics.get("SecondaryIntentF1", ""),
        "ConstraintF1 \u2191": metrics.get("ConstraintF1", ""),
        "SuppressedProtocolF1 \u2191": metrics.get("SuppressedProtocolF1", ""),
        "RiskCandidateF1 \u2191": metrics.get("RiskCandidateF1", ""),
        "_method": method,
    }


def _build_perturbation_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        method = str(summary.get("method") or "")
        if method not in MAIN_METHODS:
            continue
        metrics = summary.get("metrics")
        perturbation_metrics = (
            metrics.get("by_perturbation_type")
            if isinstance(metrics, dict)
            and isinstance(metrics.get("by_perturbation_type"), dict)
            else {}
        )
        for perturbation in PERTURBATION_ORDER:
            rows.append(
                _perturbation_row(
                    summary,
                    perturbation,
                    perturbation_metrics.get(perturbation)
                    if isinstance(perturbation_metrics, dict)
                    else None,
                )
            )
        for perturbation, row in sorted(
            perturbation_metrics.items(), key=lambda item: item[0]
        ):
            if perturbation in PERTURBATION_ORDER:
                continue
            rows.append(_perturbation_row(summary, perturbation, row))
    return sorted(
        rows,
        key=lambda row: (
            METHOD_ORDER.get(str(row["_method"]), 999),
            PERTURBATION_ORDER.index(str(row["Perturbation"]))
            if str(row["Perturbation"]) in PERTURBATION_ORDER
            else 999,
            str(row["Perturbation"]),
        ),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_md(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        cells = [str(row.get(field, "")).replace("|", "\\|") for field in fields]
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_error_analysis_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not summaries:
        return []
    return [
        {
            "Error Type": "Qualitative discussion only",
            "Description": (
                "This export is not a quantitative error analysis table. "
                "Current paper wording should describe prediction-trace review "
                "as qualitative discussion unless a future script derives error "
                "counts directly from predictions."
            ),
            "Example": "prediction trace examples",
            "Possible Cause": "N/A",
            "Future Fix": (
                "Implement prediction-derived error aggregation before reporting "
                "error-type counts or rates."
            ),
        }
    ]

def export_rair_tables(
    eval_dir: str | Path = "build/rair_eval",
    out_dir: str | Path = "build/rair_eval/tables",
) -> dict[str, Any]:
    eval_path = _resolve(eval_dir)
    out_path = _resolve(out_dir)
    summary_paths = _summaries_root(eval_path)
    summaries: list[dict[str, Any]] = []
    warnings: list[str] = []

    for path in summary_paths:
        try:
            summary = _read_json(path)
            summary["_summary_name"] = path.name
            summary["_summary_path"] = str(path)
            summaries.append(summary)
        except Exception as exc:
            warnings.append(f"skip unreadable summary {path}: {exc}")

    rows = [_table_row(summary) for summary in summaries if summary]
    main_rows = _select_main_rows(rows)
    canonical_summaries = [
        summary
        for summary in summaries
        if summary.get("_summary_name") in CANONICAL_SUMMARY_NAMES
    ]
    perturbation_rows = _build_perturbation_rows(canonical_summaries)
    ablation_rows = _select_ablation_rows(rows)
    error_rows = _build_error_analysis_rows(canonical_summaries)

    outputs = {}
    main_csv = out_path / "main_results.csv"
    by_pert_csv = out_path / "by_perturbation.csv"
    ablation_csv = out_path / "ablation_results.csv"
    error_csv = out_path / "error_analysis.csv"
    _write_csv(main_csv, main_rows, MAIN_FIELDS)
    _write_csv(by_pert_csv, perturbation_rows, PERTURBATION_FIELDS)
    _write_csv(ablation_csv, ablation_rows, MAIN_FIELDS)
    _write_md(out_path / "main_results.md", main_rows, MAIN_FIELDS)
    _write_md(
        out_path / "by_perturbation.md",
        perturbation_rows,
        PERTURBATION_FIELDS,
    )
    _write_md(out_path / "ablation_results.md", ablation_rows, MAIN_FIELDS)
    _write_csv(
        error_csv,
        error_rows,
        ["Error Type", "Description", "Example", "Possible Cause", "Future Fix"],
    )
    _write_md(
        out_path / "error_analysis.md",
        error_rows,
        ["Error Type", "Description", "Example", "Possible Cause", "Future Fix"],
    )
    outputs["main_results_csv"] = str(main_csv)
    outputs["by_perturbation_csv"] = str(by_pert_csv)
    outputs["ablation_results_csv"] = str(ablation_csv)
    outputs["error_analysis_csv"] = str(error_csv)
    outputs["main_results_md"] = str(out_path / "main_results.md")
    outputs["by_perturbation_md"] = str(out_path / "by_perturbation.md")
    outputs["ablation_results_md"] = str(out_path / "ablation_results.md")
    outputs["error_analysis_md"] = str(out_path / "error_analysis.md")

    return {
        "eval_dir": str(eval_path),
        "out_dir": str(out_path),
        "counts": {
            "main_results": len(main_rows),
            "by_perturbation": len(perturbation_rows),
            "ablation_results": len(ablation_rows),
            "error_analysis": len(error_rows),
        },
        "outputs": outputs,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export RAIR paper tables.")
    parser.add_argument("--eval-dir", default="build/rair_eval")
    parser.add_argument("--out-dir", default="build/rair_eval/tables")
    args = parser.parse_args()
    result = export_rair_tables(args.eval_dir, args.out_dir)
    for warning in result["warnings"]:
        print(f"[export_rair_tables][WARN] {warning}")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
