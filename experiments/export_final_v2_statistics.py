from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from experiments.final_v2_utils import (
    ABLATIONS,
    DATA_V2_DIR,
    DE_SEEDS,
    FINAL_V2_DIR,
    MAIN_METHODS,
    count_jsonl,
    load_summary,
    read_csv_rows,
    read_json,
    write_csv,
    write_json,
)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_row(group: str, name: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "group": group,
        "name": name,
        "num_cases": summary.get("num_cases", ""),
        "route_accuracy": summary.get("route_accuracy", ""),
        "primary_intent_accuracy": summary.get("primary_intent_accuracy", ""),
        "high_risk_recall": summary.get("high_risk_recall", ""),
        "unsafe_response_rate": summary.get("unsafe_response_rate", ""),
        "unsupported_claim_rate": summary.get("unsupported_claim_rate", ""),
        "robust_consistency": summary.get("robust_consistency", ""),
        "p95_latency_ms": summary.get("p95_latency_ms", ""),
        "summary_path": summary.get("_source", ""),
    }


def _summaries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in MAIN_METHODS:
        summary = load_summary("clean", method)
        if summary:
            rows.append(_metric_row("clean", method, summary))
    for method in MAIN_METHODS:
        summary = load_summary("robust", method)
        if summary:
            rows.append(_metric_row("robust", method, summary))
    for ablation in ABLATIONS:
        summary = load_summary("ablation", ablation)
        if summary:
            rows.append(_metric_row("ablation", ablation, summary))
    return rows


def _de_multiseed_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in DE_SEEDS:
        seed_dir = FINAL_V2_DIR / "de_multiseed" / f"seed_{seed}"
        metrics = read_json(seed_dir / "de_best_metrics.json")
        best_trial = metrics.get("best_trial")
        if not isinstance(best_trial, dict):
            best_trial = {}
        rows.append(
            {
                "seed": seed,
                "best_fitness": metrics.get("best_fitness", best_trial.get("fitness", "")),
                "policy_path": metrics.get(
                    "output_policy_path", str(seed_dir / f"policy_de_seed_{seed}.json")
                ),
                "trials_path": str(seed_dir / "de_trials.csv"),
                "curve_path": str(seed_dir / "de_curve.csv"),
                "best_metrics_path": str(seed_dir / "de_best_metrics.json"),
                "n_trials": len(read_csv_rows(seed_dir / "de_trials.csv")),
                "route_accuracy_clean": best_trial.get("route_accuracy_clean", ""),
                "route_accuracy_robust": best_trial.get("route_accuracy_robust", ""),
                "high_risk_recall": best_trial.get("high_risk_recall", ""),
                "unsafe_response_rate": best_trial.get("unsafe_response_rate", ""),
                "p95_latency_ms": best_trial.get("p95_latency_ms", ""),
            }
        )
    return rows


def _write_de_multiseed(rows: list[dict[str, Any]]) -> dict[str, str]:
    out_dir = FINAL_V2_DIR / "de_multiseed"
    csv_path = out_dir / "de_multiseed_summary.csv"
    md_path = out_dir / "de_multiseed_summary.md"
    fields = [
        "seed",
        "best_fitness",
        "n_trials",
        "route_accuracy_clean",
        "route_accuracy_robust",
        "high_risk_recall",
        "unsafe_response_rate",
        "p95_latency_ms",
        "policy_path",
        "trials_path",
        "curve_path",
        "best_metrics_path",
    ]
    write_csv(csv_path, rows, fields)
    lines = [
        "# final_v2 DE multiseed summary",
        "",
        "| seed | best_fitness | n_trials | policy_path |",
        "|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('seed')} | {row.get('best_fitness')} | {row.get('n_trials')} | {row.get('policy_path')} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"csv": str(csv_path), "markdown": str(md_path)}


def export_statistics(only_de_multiseed: bool = False) -> dict[str, Any]:
    de_rows = _de_multiseed_rows()
    de_outputs = _write_de_multiseed(de_rows)
    if only_de_multiseed:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "de_multiseed_rows": len(de_rows),
            "outputs": de_outputs,
        }

    summary_rows = _summaries()
    statistics_dir = FINAL_V2_DIR / "statistics"
    statistics_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = statistics_dir / "summary_metrics.csv"
    write_csv(
        summary_csv,
        summary_rows,
        [
            "group",
            "name",
            "num_cases",
            "route_accuracy",
            "primary_intent_accuracy",
            "high_risk_recall",
            "unsafe_response_rate",
            "unsupported_claim_rate",
            "robust_consistency",
            "p95_latency_ms",
            "summary_path",
        ],
    )
    data_counts = {
        filename: count_jsonl(DATA_V2_DIR / filename)
        for filename in (
            "clean_dev.jsonl",
            "robustness_dev.jsonl",
            "clean_test.jsonl",
            "robustness_test.jsonl",
        )
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_dir": str(FINAL_V2_DIR),
        "data_counts": data_counts,
        "summary_rows": summary_rows,
        "de_multiseed_rows": de_rows,
        "outputs": {
            "summary_metrics_csv": str(summary_csv),
            "de_multiseed_summary_csv": de_outputs["csv"],
            "de_multiseed_summary_md": de_outputs["markdown"],
        },
    }
    write_json(statistics_dir / "final_v2_statistics.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export final_v2 statistics.")
    parser.add_argument("--only-de-multiseed", action="store_true")
    args = parser.parse_args(argv)
    result = export_statistics(only_de_multiseed=args.only_de_multiseed)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
