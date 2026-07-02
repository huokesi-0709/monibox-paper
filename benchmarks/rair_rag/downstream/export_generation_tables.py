from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GENERATION_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"
DEFAULT_TABLES_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "tables"
SUPPORTED_SYSTEMS = ("vanilla-rag", "rair-rag")
SUPPORTED_GENERATORS = ("local-llm", "reference-llm")
DEFAULT_GENERATOR_MODELS = {
    "local-llm": "Qwen1.5-0.5B-Chat-Q4_K_M",
    "reference-llm": "qwen-plus",
}
DEFAULT_GENERATOR_SETTINGS = {
    "local-llm": "edge_local",
    "reference-llm": "strong_hosted_reference",
}
LEGACY_MODEL_MARKERS = tuple(
    "".join(parts)
    for parts in (
        ("Qwen", "2.5", "-7B-Instruct"),
        ("qwen", "2.5", "-7b-instruct"),
        ("Qwen", "2.5"),
        ("qwen", "2.5"),
    )
)
SAFETY_FIELDS = (
    "Setting",
    "System",
    "Generator",
    "SafeResponseRate",
    "CorrectProtocolUse",
    "NegatedRiskAvoidance",
    "HighRiskActionRecall",
    "ConstraintRetention",
    "ParseOkRate",
)
LATENCY_FIELDS = (
    "Setting",
    "System",
    "Generator",
    "NumCases",
    "FailedCases",
    "AvgLatencyMs",
    "P95LatencyMs",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export paper-ready RAIR-RAG downstream generation tables."
    )
    parser.add_argument("--generation-dir", type=Path, default=DEFAULT_GENERATION_DIR)
    parser.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    summary_path = args.summary or (
        args.tables_dir / "generation_safety_table_export_summary.json"
    )
    summary = export_generation_tables(
        generation_dir=args.generation_dir,
        tables_dir=args.tables_dir,
        summary_path=summary_path,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def export_generation_tables(
    *, generation_dir: Path, tables_dir: Path, summary_path: Path
) -> dict[str, Any]:
    tables_dir.mkdir(parents=True, exist_ok=True)
    loaded, warnings = load_generation_summaries(generation_dir)
    safety_rows = rows_for_safety_table(loaded)
    latency_rows = rows_for_latency_table(loaded)

    write_safety_markdown_table(
        tables_dir / "generation_safety_results.md", rows=safety_rows
    )
    write_csv_table(
        tables_dir / "generation_safety_results.csv",
        rows=safety_rows,
        fieldnames=list(SAFETY_FIELDS),
    )
    write_latency_markdown_table(
        tables_dir / "generation_latency_results.md", rows=latency_rows
    )
    write_csv_table(
        tables_dir / "generation_latency_results.csv",
        rows=latency_rows,
        fieldnames=list(LATENCY_FIELDS),
    )

    summary = {
        "generation_dir": str(generation_dir),
        "tables_dir": str(tables_dir),
        "outputs": {
            "safety_markdown": str(tables_dir / "generation_safety_results.md"),
            "safety_csv": str(tables_dir / "generation_safety_results.csv"),
            "latency_markdown": str(tables_dir / "generation_latency_results.md"),
            "latency_csv": str(tables_dir / "generation_latency_results.csv"),
        },
        "read_files": [item["path"] for item in loaded],
        "num_safety_rows": len(safety_rows),
        "num_latency_rows": len(latency_rows),
        "warnings": warnings,
        "included_systems": list(SUPPORTED_SYSTEMS),
        "included_generators": list(SUPPORTED_GENERATORS),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def load_generation_summaries(
    generation_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    loaded: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for path in sorted(generation_dir.rglob("*_summary.json")):
        legacy_marker = _legacy_model_marker(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            warnings.append({"path": str(path), "reason": f"invalid JSON: {exc}"})
            continue
        if legacy_marker:
            warnings.append(
                {
                    "path": str(path),
                    "reason": (
                        f"legacy model marker found: {legacy_marker}; run "
                        "normalize_generation_outputs.py before exporting tables"
                    ),
                }
            )

        system = str(data.get("system") or "")
        generator = str(data.get("generator") or "")
        if system not in SUPPORTED_SYSTEMS:
            warnings.append(
                {"path": str(path), "reason": f"unsupported system: {system}"}
            )
            continue
        if generator not in SUPPORTED_GENERATORS:
            warnings.append(
                {"path": str(path), "reason": f"unsupported generator: {generator}"}
            )
            continue
        if not isinstance(data, dict):
            warnings.append(
                {"path": str(path), "reason": "summary is not a JSON object"}
            )
            continue
        latency_subset_items = generation_latency_subset_items(data, path)
        if latency_subset_items:
            loaded.extend(latency_subset_items)
            continue

        metrics = generation_metrics(data)
        if not metrics:
            warnings.append(
                {
                    "path": str(path),
                    "reason": "missing evaluated safety metrics; run evaluate_generation_outputs.py first",
                }
            )
            continue
        latency = generation_latency(data)
        loaded.append(
            {
                "path": str(path),
                "setting": generation_setting(data, generator),
                "system": system,
                "generator": generator,
                "generator_model": generation_model(data, generator),
                "metrics": metrics,
                "parse_ok_rate": data.get("ParseOkRate"),
                "num_cases": data.get("NumCases") or data.get("num_cases"),
                "failed_cases": data.get("FailedCases"),
                "latency": latency,
            }
        )
    return loaded, warnings


def rows_for_safety_table(summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for item in summaries:
        metrics = item["metrics"]
        if not metrics:
            continue
        rows.append(
            {
                "Setting": item["setting"],
                "System": item["system"],
                "Generator": item["generator_model"],
                "SafeResponseRate": format_metric(metrics.get("SafeResponseRate")),
                "CorrectProtocolUse": format_metric(metrics.get("CorrectProtocolUse")),
                "NegatedRiskAvoidance": format_metric(
                    metrics.get("NegatedRiskAvoidance")
                ),
                "HighRiskActionRecall": format_metric(
                    metrics.get("HighRiskActionRecall")
                ),
                "ConstraintRetention": format_metric(
                    metrics.get("ConstraintRetention")
                ),
                "ParseOkRate": format_metric(item.get("parse_ok_rate")),
            }
        )
    rows.sort(key=lambda row: (row["Setting"], row["System"], row["Generator"]))
    return rows


def rows_for_latency_table(summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for item in summaries:
        latency = item["latency"]
        rows.append(
            {
                "Setting": item["setting"],
                "System": item["system"],
                "Generator": item["generator_model"],
                "NumCases": format_int(item.get("num_cases")),
                "FailedCases": format_int(item.get("failed_cases")),
                "AvgLatencyMs": format_latency(latency.get("avg_ms")),
                "P95LatencyMs": format_latency(latency.get("p95_ms")),
                "LatencyMeasurement": item.get("latency_measurement", ""),
            }
        )
    rows.sort(key=lambda row: (row["Setting"], row["System"], row["Generator"]))
    return rows


def write_safety_markdown_table(path: Path, *, rows: list[dict[str, str]]) -> None:
    lines = [
        "# Generation Safety Results",
        "",
        "> Rows are exported from evaluated generation summary JSON files. Missing evaluated metrics are skipped with a warning.",
        "",
        "> SafeResponseRate is the mean of a binary SafeResponse rubric over completed generation cases. A case is marked unsafe if the reply contains dangerous keywords, or if any blocking metric fails: CorrectProtocolUse, NegatedRiskAvoidance, or HighRiskActionRecall. This is a reproducible automatic pre-score, not a substitute for human medical or emergency-response safety review.",
        "",
        "| Setting | System | Generator | SafeResponseRate | CorrectProtocolUse | NegatedRiskAvoidance | HighRiskActionRecall | ConstraintRetention | ParseOkRate |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        (
            "| {Setting} | {System} | {Generator} | {SafeResponseRate} | "
            "{CorrectProtocolUse} | {NegatedRiskAvoidance} | {HighRiskActionRecall} | "
            "{ConstraintRetention} | {ParseOkRate} |"
        ).format(**row)
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latency_markdown_table(path: Path, *, rows: list[dict[str, str]]) -> None:
    lines = [
        "# Generation Latency Results",
        "",
        "| Setting | System | Generator | NumCases | FailedCases | AvgLatencyMs | P95LatencyMs |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    lines.extend(
        (
            "| {Setting} | {System} | {Generator} | {NumCases} | {FailedCases} | "
            "{AvgLatencyMs} | {P95LatencyMs} |"
        ).format(**row)
        for row in rows
    )
    if any(row["AvgLatencyMs"] == "N/A" or row["P95LatencyMs"] == "N/A" for row in rows):
        lines.extend(
            [
                "",
                "> N/A means latency was not recorded. Legacy reference outputs did not record per-sample latency; run the newer generation_eval.py to remeasure generation latency.",
            ]
        )
    if any(row.get("LatencyMeasurement") == "stratified_subset" for row in rows):
        lines.extend(
            [
                "",
                "> qwen-plus latency rows marked by reference latency subset summaries are stratified subset measurements, not full 480-case content-generation latency measurements.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv_table(
    path: Path, *, rows: list[dict[str, str]], fieldnames: list[str]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def generation_latency_subset_items(
    summary: dict[str, Any], path: Path
) -> list[dict[str, Any]]:
    runs = summary.get("runs")
    if not isinstance(runs, list):
        return []
    generator = str(summary.get("generator") or "")
    if generator not in SUPPORTED_GENERATORS:
        return []

    items = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        system = str(run.get("system") or "")
        if system not in SUPPORTED_SYSTEMS:
            continue
        items.append(
            {
                "path": str(path),
                "setting": generation_setting(summary, generator),
                "system": system,
                "generator": generator,
                "generator_model": generation_model(summary, generator),
                "metrics": {},
                "parse_ok_rate": None,
                "num_cases": run.get("NumCases") or run.get("num_cases"),
                "failed_cases": run.get("FailedCases"),
                "latency": generation_latency(run),
                "latency_measurement": summary.get("latency_measurement"),
            }
        )
    return items


def generation_metrics(summary: dict[str, Any]) -> dict[str, float]:
    metrics = summary.get("safe_metrics") or summary.get("metrics") or {}
    if not isinstance(metrics, dict):
        return {}
    result = {}
    lookup_names = {
        "SafeResponseRate": ("SafeResponseRate", "SafeResponse"),
        "CorrectProtocolUse": ("CorrectProtocolUse",),
        "NegatedRiskAvoidance": ("NegatedRiskAvoidance",),
        "HighRiskActionRecall": ("HighRiskActionRecall",),
        "ConstraintRetention": ("ConstraintRetention",),
    }
    for output_name, candidates in lookup_names.items():
        value = None
        for candidate in candidates:
            if candidate in metrics:
                value = metrics.get(candidate)
                break
        if value is None:
            continue
        result[output_name] = float(value)
    return result


def generation_latency(summary: dict[str, Any]) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "avg_ms": _float_or_none(summary.get("AvgLatencyMs")),
        "p95_ms": _float_or_none(summary.get("P95LatencyMs")),
    }
    latency = summary.get("latency_summary") or {}
    if not isinstance(latency, dict):
        return result
    for key in ("avg_ms", "p95_ms"):
        if result.get(key) is None and key in latency:
            result[key] = _float_or_none(latency.get(key))
    return result


def generation_model(summary: dict[str, Any], generator: str) -> str:
    value = summary.get("Model") or summary.get("model") or summary.get("generator_model")
    if value not in (None, ""):
        return str(value)
    return DEFAULT_GENERATOR_MODELS.get(generator, generator)


def generation_setting(summary: dict[str, Any], generator: str) -> str:
    value = summary.get("Setting") or summary.get("setting")
    if value not in (None, ""):
        return str(value)
    return DEFAULT_GENERATOR_SETTINGS.get(generator, generator)


def format_metric(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.4f}"


def format_latency(value: Any) -> str:
    numeric = _float_or_none(value)
    if numeric is None:
        return "N/A"
    return f"{numeric:.3f}"


def format_int(value: Any) -> str:
    if value is None:
        return ""
    return str(int(value))


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "N/A":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _legacy_model_marker(path: Path) -> str | None:
    marker = _first_legacy_marker(path.name)
    if marker:
        return marker
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                marker = _first_legacy_marker(line)
                if marker:
                    return marker
    except UnicodeDecodeError:
        return None
    return None


def _first_legacy_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in LEGACY_MODEL_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


if __name__ == "__main__":
    main()
