from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from experiments.final_v2_utils import (
    ABLATIONS,
    DATA_V2_DIR,
    FINAL_V2_DIR,
    MAIN_METHODS,
    read_csv_rows,
    read_jsonl,
    write_csv,
    write_json,
    write_markdown_table,
)


TABLE_DIR = FINAL_V2_DIR / "tables"
STAT_DIR = FINAL_V2_DIR / "statistics"
METHOD_LABELS = {
    "vanilla-rag": "Vanilla-RAG",
    "rag-guard": "RAG-Guard",
    "hsc-rag-manual": "HSC-RAG-manual",
    "hsc-rag-de": "HSC-RAG-DE",
}
ABLATION_EFFECTS = {
    "without_input_normalization": "Input normalization",
    "without_multi_intent": "Multi-intent routing",
    "without_negation": "Negation handling",
    "without_protocol_gate": "Protocol gate",
    "without_safety_rerank": "Safety rerank",
    "without_low_evidence": "Low-evidence routing",
    "without_guard": "Guard module",
    "without_de_optimization": "DE optimization",
}


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, latency: bool = False) -> str:
    number = _num(value)
    if number is None:
        return ""
    return f"{number:.2f}" if latency else f"{number:.4f}"


def _rows_by_group_name(path_name: str) -> dict[tuple[str, str], dict[str, Any]]:
    rows = read_csv_rows(STAT_DIR / path_name)
    return {(str(row.get("group")), str(row.get("name"))): row for row in rows}


def _metric(row: dict[str, Any] | None, key: str, latency: bool = False) -> str:
    return _fmt((row or {}).get(key), latency=latency)


def _raw(row: dict[str, Any] | None, key: str) -> Any:
    return "" if row is None else row.get(key, "")


def _write_table(name: str, rows: list[dict[str, Any]], fields: list[str]) -> dict[str, str]:
    csv_path = TABLE_DIR / f"{name}.csv"
    md_path = TABLE_DIR / f"{name}.md"
    write_csv(csv_path, rows, fields)
    write_markdown_table(md_path, rows, fields)
    return {"csv": str(csv_path), "md": str(md_path), "rows": len(rows)}


def _dataset_distribution() -> list[dict[str, Any]]:
    split_rows: dict[str, dict[str, Any]] = {
        "dev": {"split": "dev", "clean_count": 0, "robust_count": 0, "total_count": 0},
        "test": {"split": "test", "clean_count": 0, "robust_count": 0, "total_count": 0},
    }
    risk: dict[str, Counter[str]] = defaultdict(Counter)
    scenario: dict[str, Counter[str]] = defaultdict(Counter)
    perturbation: dict[str, Counter[str]] = defaultdict(Counter)
    for filename in ("clean_dev.jsonl", "robustness_dev.jsonl", "clean_test.jsonl", "robustness_test.jsonl"):
        rows = read_jsonl(DATA_V2_DIR / filename)
        for row in rows:
            split = str(row.get("split") or ("dev" if "dev" in filename else "test"))
            ptype = str(row.get("perturbation_type") or "")
            if ptype == "clean":
                split_rows[split]["clean_count"] += 1
            else:
                split_rows[split]["robust_count"] += 1
            split_rows[split]["total_count"] += 1
            risk[split][str(row.get("risk_level") or "")] += 1
            scenario[split][str(row.get("scenario_family") or "")] += 1
            perturbation[split][ptype] += 1
    out = []
    for split in ("dev", "test"):
        out.append(
            {
                **split_rows[split],
                "risk_distribution": json.dumps(dict(sorted(risk[split].items())), ensure_ascii=False),
                "scenario_family_distribution": json.dumps(dict(sorted(scenario[split].items())), ensure_ascii=False),
                "perturbation_distribution": json.dumps(dict(sorted(perturbation[split].items())), ensure_ascii=False),
            }
        )
    return out


def _table11(metrics: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in MAIN_METHODS:
        clean = metrics.get(("clean", method))
        robust = metrics.get(("robust", method))
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Clean RouteAcc": _metric(clean, "RouteAcc"),
                "Clean HRR": _metric(clean, "HRR"),
                "Clean URR": _metric(clean, "URR"),
                "Robust RouteAcc": _metric(robust, "RouteAcc"),
                "Robust HRR": _metric(robust, "HRR"),
                "Robust URR": _metric(robust, "URR"),
                "RC": _metric(robust, "RC"),
                "P95 Latency": _metric(robust, "p95_latency_ms", latency=True),
            }
        )
    return rows


def _table12(metrics: dict[tuple[str, str], dict[str, Any]], perturbation_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_method_type = {
        (str(row.get("method")), str(row.get("perturbation_type"))): row
        for row in perturbation_rows
    }
    rows = []
    for method in MAIN_METHODS:
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Clean RouteAcc": _metric(metrics.get(("clean", method)), "RouteAcc"),
                "Filler Noise RouteAcc": _metric(by_method_type.get((method, "filler_noise")), "RouteAcc"),
                "Long Context RouteAcc": _metric(by_method_type.get((method, "long_context")), "RouteAcc"),
                "Repetition RouteAcc": _metric(by_method_type.get((method, "repetition")), "RouteAcc"),
            }
        )
    return rows


def _table13(ablation_metrics: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for ablation in ABLATIONS:
        row = ablation_metrics.get(("ablation", ablation))
        rows.append(
            {
                "Ablation": ablation,
                "RouteAcc": _metric(row, "RouteAcc"),
                "ProtocolAcc": _metric(row, "ProtocolAcc"),
                "HRR": _metric(row, "HRR"),
                "URR": _metric(row, "URR"),
                "UCR": _metric(row, "UCR"),
                "RC": _metric(row, "RC"),
                "P95 Latency": _metric(row, "p95_latency_ms", latency=True),
                "Main Effect": ABLATION_EFFECTS.get(ablation, ""),
            }
        )
    return rows


def _delta(left: Any, right: Any, latency: bool = False) -> str:
    a = _num(left)
    b = _num(right)
    if a is None or b is None:
        return ""
    return _fmt(b - a, latency=latency)


def _table14(metrics: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for split in ("clean", "robust"):
        manual = metrics.get((split, "hsc-rag-manual"))
        de = metrics.get((split, "hsc-rag-de"))
        rows.append(
            {
                "Split": split,
                "Manual RouteAcc": _metric(manual, "RouteAcc"),
                "DE RouteAcc": _metric(de, "RouteAcc"),
                "ΔRouteAcc": _delta(_raw(manual, "RouteAcc"), _raw(de, "RouteAcc")),
                "Manual HRR": _metric(manual, "HRR"),
                "DE HRR": _metric(de, "HRR"),
                "ΔHRR": _delta(_raw(manual, "HRR"), _raw(de, "HRR")),
                "Manual URR": _metric(manual, "URR"),
                "DE URR": _metric(de, "URR"),
                "ΔURR": _delta(_raw(manual, "URR"), _raw(de, "URR")),
                "Manual P95": _metric(manual, "p95_latency_ms", latency=True),
                "DE P95": _metric(de, "p95_latency_ms", latency=True),
                "ΔP95": _delta(_raw(manual, "p95_latency_ms"), _raw(de, "p95_latency_ms"), latency=True),
            }
        )
    return rows


def _table15(metrics: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in MAIN_METHODS:
        clean = metrics.get(("clean", method))
        robust = metrics.get(("robust", method))
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Clean HRR": _metric(clean, "HRR"),
                "Clean HMR": _metric(clean, "HMR"),
                "Clean URR": _metric(clean, "URR"),
                "Clean UCR": _metric(clean, "UCR"),
                "Robust HRR": _metric(robust, "HRR"),
                "Robust HMR": _metric(robust, "HMR"),
                "Robust URR": _metric(robust, "URR"),
                "Robust UCR": _metric(robust, "UCR"),
            }
        )
    return rows


def _table16(metrics: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in MAIN_METHODS:
        robust = metrics.get(("robust", method))
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Avg Latency": _metric(robust, "avg_latency_ms", latency=True),
                "P95 Latency": _metric(robust, "p95_latency_ms", latency=True),
                "Avg Response Length": _metric(robust, "avg_response_length", latency=True),
            }
        )
    return rows


def _table17(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Group": row.get("group", ""),
            "Name": row.get("name", ""),
            "Metric": row.get("metric", ""),
            "Mean": _fmt(row.get("mean")),
            "CI Lower": _fmt(row.get("ci_lower")),
            "CI Upper": _fmt(row.get("ci_upper")),
            "N": row.get("n", ""),
        }
        for row in rows
    ]


def _table18() -> list[dict[str, Any]]:
    summary_path = FINAL_V2_DIR / "human_review" / "digital_review_summary.csv"
    review_rows = read_csv_rows(summary_path)
    if review_rows:
        return review_rows
    balanced_report_path = FINAL_V2_DIR / "human_review" / "disagreement_report_balanced_300.json"
    if balanced_report_path.exists():
        report = json.loads(balanced_report_path.read_text(encoding="utf-8"))
        scores = report.get("final_scores_by_method", {})
        rows = []
        for method in MAIN_METHODS:
            row = scores.get(method, {})
            rows.append(
                {
                    "Method": METHOD_LABELS[method],
                    "Review Count": row.get("review_count", ""),
                    "Final Safety Score": _fmt(row.get("final_safety_score")),
                    "Final Usefulness Score": _fmt(row.get("final_usefulness_score")),
                    "Final Brevity Score": _fmt(row.get("final_brevity_score")),
                    "Route Correct Rate": _fmt(row.get("final_route_correct_rate")),
                    "Protocol Correct Rate": _fmt(row.get("final_protocol_correct_rate")),
                    "Unsafe Action Rate": _fmt(row.get("final_contains_unsafe_action_rate")),
                    "Unsupported Claim Rate": _fmt(row.get("final_unsupported_claim_rate")),
                }
            )
        write_csv(
            summary_path,
            rows,
            [
                "Method",
                "Review Count",
                "Final Safety Score",
                "Final Usefulness Score",
                "Final Brevity Score",
                "Route Correct Rate",
                "Protocol Correct Rate",
                "Unsafe Action Rate",
                "Unsupported Claim Rate",
            ],
        )
        return rows
    return [
        {
            "Method": METHOD_LABELS[method],
            "Review Count": "",
            "Final Safety Score": "",
            "Final Usefulness Score": "",
            "Final Brevity Score": "",
            "Route Correct Rate": "",
            "Protocol Correct Rate": "",
            "Unsafe Action Rate": "",
            "Unsupported Claim Rate": "",
        }
        for method in MAIN_METHODS
    ]


def _write_all_md(outputs: dict[str, dict[str, Any]]) -> str:
    path = TABLE_DIR / "paper_tables_all.md"
    sections = [
        ("数据集分布", "table_dataset_distribution.md"),
        ("表 11：整体性能", "table11_overall_performance.md"),
        ("表 12：扰动类型分析", "table12_perturbation_results.md"),
        ("表 13：消融实验", "table13_ablation_results.md"),
        ("表 14：DE 效果", "table14_de_effect.md"),
        ("表 15：安全性指标", "table15_safety_metrics.md"),
        ("表 16：效率指标", "table16_efficiency.md"),
        ("表 17：Bootstrap 95% CI", "table17_bootstrap_ci.md"),
        ("表 18：数字复核", "table18_digital_review.md"),
    ]
    lines = ["# final_v2 论文第 4 章表格汇总", ""]
    for title, filename in sections:
        lines.append(f"## {title}")
        lines.append("")
        table_path = TABLE_DIR / filename
        if table_path.exists():
            lines.append(table_path.read_text(encoding="utf-8").strip())
        else:
            lines.append("_表格尚未生成。_")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(path)


def export_tables() -> dict[str, Any]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    metrics = _rows_by_group_name("final_metrics_by_method.csv")
    ablation_metrics = _rows_by_group_name("ablation_metrics.csv")
    perturbation = read_csv_rows(STAT_DIR / "perturbation_metrics.csv")
    bootstrap = read_csv_rows(STAT_DIR / "bootstrap_ci.csv")

    outputs: dict[str, dict[str, Any]] = {}
    outputs["table_dataset_distribution"] = _write_table(
        "table_dataset_distribution",
        _dataset_distribution(),
        ["split", "clean_count", "robust_count", "total_count", "risk_distribution", "scenario_family_distribution", "perturbation_distribution"],
    )
    outputs["table11_overall_performance"] = _write_table(
        "table11_overall_performance",
        _table11(metrics),
        ["Method", "Clean RouteAcc", "Clean HRR", "Clean URR", "Robust RouteAcc", "Robust HRR", "Robust URR", "RC", "P95 Latency"],
    )
    outputs["table12_perturbation_results"] = _write_table(
        "table12_perturbation_results",
        _table12(metrics, perturbation),
        ["Method", "Clean RouteAcc", "Filler Noise RouteAcc", "Long Context RouteAcc", "Repetition RouteAcc"],
    )
    outputs["table13_ablation_results"] = _write_table(
        "table13_ablation_results",
        _table13(ablation_metrics),
        ["Ablation", "RouteAcc", "ProtocolAcc", "HRR", "URR", "UCR", "RC", "P95 Latency", "Main Effect"],
    )
    outputs["table14_de_effect"] = _write_table(
        "table14_de_effect",
        _table14(metrics),
        ["Split", "Manual RouteAcc", "DE RouteAcc", "ΔRouteAcc", "Manual HRR", "DE HRR", "ΔHRR", "Manual URR", "DE URR", "ΔURR", "Manual P95", "DE P95", "ΔP95"],
    )
    outputs["table15_safety_metrics"] = _write_table(
        "table15_safety_metrics",
        _table15(metrics),
        ["Method", "Clean HRR", "Clean HMR", "Clean URR", "Clean UCR", "Robust HRR", "Robust HMR", "Robust URR", "Robust UCR"],
    )
    outputs["table16_efficiency"] = _write_table(
        "table16_efficiency",
        _table16(metrics),
        ["Method", "Avg Latency", "P95 Latency", "Avg Response Length"],
    )
    outputs["table17_bootstrap_ci"] = _write_table(
        "table17_bootstrap_ci",
        _table17(bootstrap),
        ["Group", "Name", "Metric", "Mean", "CI Lower", "CI Upper", "N"],
    )
    outputs["table18_digital_review"] = _write_table(
        "table18_digital_review",
        _table18(),
        ["Method", "Review Count", "Final Safety Score", "Final Usefulness Score", "Final Brevity Score", "Route Correct Rate", "Protocol Correct Rate", "Unsafe Action Rate", "Unsupported Claim Rate"],
    )
    paper_all = _write_all_md(outputs)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "statistics_dir": str(STAT_DIR),
        "tables_dir": str(TABLE_DIR),
        "outputs": outputs,
        "paper_tables_all": paper_all,
    }
    write_json(TABLE_DIR / "final_v2_tables_export_report.json", report)
    return report


def main() -> int:
    report = export_tables()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
