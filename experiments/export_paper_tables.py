from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


METHOD_ORDER = ("vanilla-rag", "rag-guard", "hsc-rag-manual", "hsc-rag-de")
METHOD_DISPLAY = {
    "vanilla-rag": "Vanilla-RAG",
    "rag-guard": "RAG-Guard",
    "hsc-rag-manual": "HSC-RAG-manual",
    "hsc-rag-de": "HSC-RAG-DE",
}
ABLATION_ORDER = (
    "without_input_normalization",
    "without_multi_intent",
    "without_negation",
    "without_protocol_gate",
    "without_safety_rerank",
    "without_low_evidence",
    "without_guard",
    "without_de_optimization",
)
ABLATION_AFFECTED_METRICS = {
    "without_input_normalization": "RouteAcc, RC",
    "without_multi_intent": "RouteAcc, HRR",
    "without_negation": "HRR, UCR",
    "without_protocol_gate": "RouteAcc, HRR",
    "without_safety_rerank": "URR, UCR",
    "without_low_evidence": "UCR, HRR",
    "without_guard": "URR, UCR",
    "without_de_optimization": "RouteAcc, HRR, URR, RC",
}
PERTURBATION_ORDER = ("filler_noise", "long_context", "repetition")

TABLE_FIELDS = {
    "table11_overall_performance": [
        "Method",
        "Clean RouteAcc",
        "Clean HRR",
        "Clean URR",
        "Robust RouteAcc",
        "Robust HRR",
        "Robust URR",
        "RC",
        "P95 Latency",
    ],
    "table12_perturbation_route_accuracy": [
        "Method",
        "Clean RouteAcc",
        "Filler Noise RouteAcc",
        "Long Context RouteAcc",
        "Repetition RouteAcc",
    ],
    "table13_ablation_results": [
        "Method",
        "Main Affected Metrics",
        "RouteAcc",
        "HRR",
        "URR",
        "UCR",
        "RC",
        "P95 Latency",
    ],
    "table14_de_effect": [
        "Split",
        "ΔRouteAcc",
        "ΔHRR",
        "ΔURR",
        "ΔUCR",
        "ΔRC",
        "ΔP95 Latency",
    ],
    "table15_safety_metrics": [
        "Method",
        "Clean HRR",
        "Clean HMR",
        "Clean URR",
        "Clean UCR",
        "Robust HRR",
        "Robust HMR",
        "Robust URR",
        "Robust UCR",
    ],
    "table16_efficiency": [
        "Method",
        "Avg Latency (ms)",
        "P95 Latency (ms)",
        "Avg Response Length",
    ],
}

TABLE_FILENAMES = {
    "table11_overall_performance": "table11_overall_performance.csv",
    "table12_perturbation_route_accuracy": "table12_perturbation_route_accuracy.csv",
    "table13_ablation_results": "table13_ablation_results.csv",
    "table14_de_effect": "table14_de_effect.csv",
    "table15_safety_metrics": "table15_safety_metrics.csv",
    "table16_efficiency": "table16_efficiency.csv",
}

TABLE_TITLES = {
    "table11_overall_performance": "表 11 整体性能",
    "table12_perturbation_route_accuracy": "表 12 不同扰动类型 RouteAcc",
    "table13_ablation_results": "表 13 消融实验",
    "table14_de_effect": "表 14 DE 相对人工权重变化",
    "table15_safety_metrics": "表 15 安全性指标",
    "table16_efficiency": "表 16 效率指标",
}

LATENCY_FIELDS = {"P95 Latency", "ΔP95 Latency", "Avg Latency (ms)", "P95 Latency (ms)"}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _read_csv_first_row(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return dict(rows[0]) if rows else {}


def _summary_key(path: Path) -> str:
    name = path.name
    for suffix in ("_summary.json", "_summary.csv"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _normalize_method(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "vanilla_rag": "vanilla-rag",
        "rag_guard": "rag-guard",
        "hsc_rag_manual": "hsc-rag-manual",
        "hsc_rag_de": "hsc-rag-de",
    }
    return aliases.get(text, text)


def _method_from_path(path: Path) -> str:
    key = _summary_key(path)
    for method in METHOD_ORDER:
        if key == method or key.endswith(method) or method in key:
            return method
    return _normalize_method(key)


def _split_from_path(path: Path, row: dict[str, Any]) -> str:
    source = str(path).replace("\\", "/").lower()
    data = str(row.get("data") or "").replace("\\", "/").lower()
    text = f"{source} {data}"
    if "/ablation/" in text or "ablation" in text:
        return "ablation"
    if "/robust/" in text or "robustness_test" in text or "robust_test" in text:
        return "robust"
    if "/clean/" in text or "clean_test" in text:
        return "clean"
    return "unknown"


def _load_summaries(eval_dir: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
    warnings: list[str] = []
    summaries: dict[str, dict[str, dict[str, Any]]] = {
        "clean": {},
        "robust": {},
        "ablation": {},
    }
    seen_keys: set[tuple[str, str]] = set()

    for path in sorted(eval_dir.rglob("*_summary.json")):
        try:
            row = _read_json(path)
        except Exception as exc:
            warnings.append(f"无法读取 summary JSON：{path}；原因：{exc}")
            continue
        method = _normalize_method(row.get("ablation") or row.get("method") or _method_from_path(path))
        split = _split_from_path(path, row)
        row["_source"] = str(path)
        row["_method_key"] = method
        row["_split"] = split
        if split in summaries:
            summaries[split][method] = row
            seen_keys.add((split, method))

    for path in sorted(eval_dir.rglob("*_summary.csv")):
        try:
            row = _read_csv_first_row(path)
        except Exception as exc:
            warnings.append(f"无法读取 summary CSV：{path}；原因：{exc}")
            continue
        if not row:
            warnings.append(f"summary CSV 为空：{path}")
            continue
        method = _normalize_method(row.get("ablation") or row.get("method") or _method_from_path(path))
        split = _split_from_path(path, row)
        if (split, method) in seen_keys:
            continue
        row["_source"] = str(path)
        row["_method_key"] = method
        row["_split"] = split
        if split in summaries:
            summaries[split][method] = row
            seen_keys.add((split, method))

    return summaries, warnings


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric(
    row: dict[str, Any] | None,
    key: str,
    table: str,
    method: str,
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> float | None:
    if row is None:
        label = f"{method}.{key}"
        missing_fields[table].append(label)
        warnings.append(f"{table}: 缺少 {method} 的 summary，字段 {key} 置空")
        return None
    if key not in row or row.get(key) in (None, ""):
        label = f"{method}.{key}"
        missing_fields[table].append(label)
        warnings.append(f"{table}: {row.get('_source', method)} 缺少字段 {key}，置空")
        return None
    value = _to_float(row.get(key))
    if value is None:
        label = f"{method}.{key}"
        missing_fields[table].append(label)
        warnings.append(f"{table}: 字段 {key} 不是数值：{row.get(key)!r}，置空")
    return value


def _format_value(value: Any, field: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    number = _to_float(value)
    if number is None:
        return str(value)
    if field in LATENCY_FIELDS:
        return f"{number:.2f}"
    return f"{number:.4f}"


def _display_method(method: str) -> str:
    return METHOD_DISPLAY.get(method, method)


def _prediction_method(path: Path, row: dict[str, Any]) -> str:
    method = _normalize_method(row.get("method"))
    if method:
        return method
    name = path.name
    for candidate in METHOD_ORDER:
        if candidate in name:
            return candidate
    return _normalize_method(path.stem.replace("_predictions", ""))


def _trace(row: dict[str, Any]) -> dict[str, Any]:
    trace = row.get("trace")
    return trace if isinstance(trace, dict) else {}


def _predicted_route(row: dict[str, Any]) -> str:
    trace = _trace(row)
    return str(
        row.get("predicted_route")
        or trace.get("route_name")
        or trace.get("primary_intent")
        or row.get("primary_intent")
        or ""
    )


def _case(row: dict[str, Any]) -> dict[str, Any]:
    case = row.get("case")
    return case if isinstance(case, dict) else {}


def _expected_route(row: dict[str, Any]) -> str:
    case = _case(row)
    return str(row.get("expected_route") or case.get("expected_route") or "")


def _perturbation_type(row: dict[str, Any]) -> str:
    case = _case(row)
    return str(row.get("perturbation_type") or case.get("perturbation_type") or "")


def _load_robust_prediction_route_accuracy(eval_dir: Path, warnings: list[str]) -> dict[str, dict[str, float]]:
    robust_dir = eval_dir / "robust"
    grouped: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    paths = sorted(robust_dir.rglob("*_predictions.jsonl")) if robust_dir.exists() else []
    if not paths:
        warnings.append(f"表12: 未找到 robust predictions：{robust_dir}")
        return {}

    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    warnings.append(f"表12: 跳过非法 JSONL：{path}:line {lineno}；原因：{exc}")
                    continue
                if not isinstance(row, dict):
                    warnings.append(f"表12: 跳过非对象 prediction：{path}:line {lineno}")
                    continue
                method = _prediction_method(path, row)
                perturbation = _perturbation_type(row)
                expected = _expected_route(row)
                predicted = _predicted_route(row)
                if not perturbation or not expected:
                    warnings.append(f"表12: {path}:line {lineno} 缺少 perturbation_type 或 expected_route")
                    continue
                grouped[method][perturbation].append(predicted == expected)

    result: dict[str, dict[str, float]] = {}
    for method, by_type in grouped.items():
        result[method] = {}
        for perturbation, hits in by_type.items():
            result[method][perturbation] = sum(1 for hit in hits if hit) / len(hits) if hits else 0.0
    return result


def _build_table11(
    summaries: dict[str, dict[str, dict[str, Any]]],
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    table = "table11_overall_performance"
    rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        clean = summaries["clean"].get(method)
        robust = summaries["robust"].get(method)
        rows.append(
            {
                "Method": _display_method(method),
                "Clean RouteAcc": _metric(clean, "route_accuracy", table, method, missing_fields, warnings),
                "Clean HRR": _metric(clean, "high_risk_recall", table, method, missing_fields, warnings),
                "Clean URR": _metric(clean, "unsafe_response_rate", table, method, missing_fields, warnings),
                "Robust RouteAcc": _metric(robust, "route_accuracy", table, method, missing_fields, warnings),
                "Robust HRR": _metric(robust, "high_risk_recall", table, method, missing_fields, warnings),
                "Robust URR": _metric(robust, "unsafe_response_rate", table, method, missing_fields, warnings),
                "RC": _metric(robust, "robust_consistency", table, method, missing_fields, warnings),
                "P95 Latency": _metric(robust, "p95_latency_ms", table, method, missing_fields, warnings),
            }
        )
    return rows


def _build_table12(
    summaries: dict[str, dict[str, dict[str, Any]]],
    perturbation_acc: dict[str, dict[str, float]],
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    table = "table12_perturbation_route_accuracy"
    rows: list[dict[str, Any]] = []
    field_by_type = {
        "filler_noise": "Filler Noise RouteAcc",
        "long_context": "Long Context RouteAcc",
        "repetition": "Repetition RouteAcc",
    }
    for method in METHOD_ORDER:
        clean = summaries["clean"].get(method)
        row: dict[str, Any] = {
            "Method": _display_method(method),
            "Clean RouteAcc": _metric(clean, "route_accuracy", table, method, missing_fields, warnings),
        }
        for perturbation in PERTURBATION_ORDER:
            value = perturbation_acc.get(method, {}).get(perturbation)
            if value is None:
                missing_fields[table].append(f"{method}.{perturbation}.route_accuracy")
                warnings.append(f"{table}: 缺少 {method} 的 {perturbation} predictions 统计，置空")
            row[field_by_type[perturbation]] = value
        rows.append(row)
    return rows


def _build_table13(
    summaries: dict[str, dict[str, dict[str, Any]]],
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    table = "table13_ablation_results"
    rows: list[dict[str, Any]] = []
    for ablation in ABLATION_ORDER:
        row = summaries["ablation"].get(ablation)
        rows.append(
            {
                "Method": ablation,
                "Main Affected Metrics": ABLATION_AFFECTED_METRICS.get(ablation, ""),
                "RouteAcc": _metric(row, "route_accuracy", table, ablation, missing_fields, warnings),
                "HRR": _metric(row, "high_risk_recall", table, ablation, missing_fields, warnings),
                "URR": _metric(row, "unsafe_response_rate", table, ablation, missing_fields, warnings),
                "UCR": _metric(row, "unsupported_claim_rate", table, ablation, missing_fields, warnings),
                "RC": _metric(row, "robust_consistency", table, ablation, missing_fields, warnings),
                "P95 Latency": _metric(row, "p95_latency_ms", table, ablation, missing_fields, warnings),
            }
        )
    return rows


def _delta(
    de_row: dict[str, Any] | None,
    manual_row: dict[str, Any] | None,
    metric: str,
    table: str,
    split: str,
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> float | None:
    de_value = _metric(de_row, metric, table, f"{split}.hsc-rag-de", missing_fields, warnings)
    manual_value = _metric(
        manual_row, metric, table, f"{split}.hsc-rag-manual", missing_fields, warnings
    )
    if de_value is None or manual_value is None:
        return None
    return de_value - manual_value


def _build_table14(
    summaries: dict[str, dict[str, dict[str, Any]]],
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    table = "table14_de_effect"
    rows: list[dict[str, Any]] = []
    for split in ("clean", "robust"):
        de_row = summaries[split].get("hsc-rag-de")
        manual_row = summaries[split].get("hsc-rag-manual")
        rows.append(
            {
                "Split": split,
                "ΔRouteAcc": _delta(de_row, manual_row, "route_accuracy", table, split, missing_fields, warnings),
                "ΔHRR": _delta(de_row, manual_row, "high_risk_recall", table, split, missing_fields, warnings),
                "ΔURR": _delta(de_row, manual_row, "unsafe_response_rate", table, split, missing_fields, warnings),
                "ΔUCR": _delta(de_row, manual_row, "unsupported_claim_rate", table, split, missing_fields, warnings),
                "ΔRC": _delta(de_row, manual_row, "robust_consistency", table, split, missing_fields, warnings),
                "ΔP95 Latency": _delta(de_row, manual_row, "p95_latency_ms", table, split, missing_fields, warnings),
            }
        )
    return rows


def _hmr(hrr: float | None) -> float | None:
    return None if hrr is None else 1.0 - hrr


def _build_table15(
    summaries: dict[str, dict[str, dict[str, Any]]],
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    table = "table15_safety_metrics"
    rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        clean = summaries["clean"].get(method)
        robust = summaries["robust"].get(method)
        clean_hrr = _metric(clean, "high_risk_recall", table, method, missing_fields, warnings)
        robust_hrr = _metric(robust, "high_risk_recall", table, method, missing_fields, warnings)
        rows.append(
            {
                "Method": _display_method(method),
                "Clean HRR": clean_hrr,
                "Clean HMR": _hmr(clean_hrr),
                "Clean URR": _metric(clean, "unsafe_response_rate", table, method, missing_fields, warnings),
                "Clean UCR": _metric(clean, "unsupported_claim_rate", table, method, missing_fields, warnings),
                "Robust HRR": robust_hrr,
                "Robust HMR": _hmr(robust_hrr),
                "Robust URR": _metric(robust, "unsafe_response_rate", table, method, missing_fields, warnings),
                "Robust UCR": _metric(robust, "unsupported_claim_rate", table, method, missing_fields, warnings),
            }
        )
    return rows


def _build_table16(
    summaries: dict[str, dict[str, dict[str, Any]]],
    missing_fields: dict[str, list[str]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    table = "table16_efficiency"
    rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        robust = summaries["robust"].get(method)
        rows.append(
            {
                "Method": _display_method(method),
                "Avg Latency (ms)": _metric(robust, "avg_latency_ms", table, method, missing_fields, warnings),
                "P95 Latency (ms)": _metric(robust, "p95_latency_ms", table, method, missing_fields, warnings),
                "Avg Response Length": _metric(robust, "avg_response_length", table, method, missing_fields, warnings),
            }
        )
    return rows


def _formatted_rows(table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    fields = TABLE_FIELDS[table_name]
    return [{field: _format_value(row.get(field), field) for field in fields} for row in rows]


def _write_csv(path: Path, table_name: str, rows: list[dict[str, Any]]) -> None:
    fields = TABLE_FIELDS[table_name]
    formatted = _formatted_rows(table_name, rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(formatted)


def _markdown_table(table_name: str, rows: list[dict[str, Any]]) -> str:
    fields = TABLE_FIELDS[table_name]
    formatted = _formatted_rows(table_name, rows)
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in formatted:
        cells = [str(row.get(field, "")).replace("|", "\\|") for field in fields]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _write_paper_tables(path: Path, tables: dict[str, list[dict[str, Any]]]) -> None:
    lines = ["# 论文第 4 章结果表", ""]
    for table_name in TABLE_FILENAMES:
        lines.append(f"## {TABLE_TITLES[table_name]}")
        lines.append("")
        lines.append(_markdown_table(table_name, tables[table_name]))
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def export_paper_tables(
    eval_dir: str | Path = "build/eval/test",
    out_dir: str | Path = "build/eval/test/tables",
) -> dict[str, Any]:
    eval_path = _resolve(eval_dir)
    out_path = _resolve(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    missing_fields: dict[str, list[str]] = defaultdict(list)
    summaries, summary_warnings = _load_summaries(eval_path)
    warnings.extend(summary_warnings)
    perturbation_acc = _load_robust_prediction_route_accuracy(eval_path, warnings)

    tables = {
        "table11_overall_performance": _build_table11(summaries, missing_fields, warnings),
        "table12_perturbation_route_accuracy": _build_table12(
            summaries, perturbation_acc, missing_fields, warnings
        ),
        "table13_ablation_results": _build_table13(summaries, missing_fields, warnings),
        "table14_de_effect": _build_table14(summaries, missing_fields, warnings),
        "table15_safety_metrics": _build_table15(summaries, missing_fields, warnings),
        "table16_efficiency": _build_table16(summaries, missing_fields, warnings),
    }

    outputs: dict[str, str] = {}
    for table_name, filename in TABLE_FILENAMES.items():
        path = out_path / filename
        _write_csv(path, table_name, tables[table_name])
        outputs[table_name] = str(path)

    md_path = out_path / "paper_tables.md"
    _write_paper_tables(md_path, tables)
    outputs["paper_tables"] = str(md_path)

    report = {
        "eval_dir": str(eval_path),
        "out_dir": str(out_path),
        "outputs": outputs,
        "table_rows": {name: len(rows) for name, rows in tables.items()},
        "missing_fields": {name: values for name, values in sorted(missing_fields.items())},
        "warnings": warnings,
        "loaded_summary_counts": {split: len(rows) for split, rows in summaries.items()},
    }
    report_path = out_path / "export_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    outputs["export_report"] = str(report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export paper chapter 4 tables from test evaluation outputs.")
    parser.add_argument("--eval-dir", default="build/eval/test")
    parser.add_argument("--out-dir", default="build/eval/test/tables")
    args = parser.parse_args(argv)

    report = export_paper_tables(args.eval_dir, args.out_dir)
    for warning in report["warnings"]:
        print(f"[export_paper_tables][WARN] {warning}")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
