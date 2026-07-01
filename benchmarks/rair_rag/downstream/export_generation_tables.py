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
DATASET_LABELS = {"rair_test": "main", "rair_test_multi_intent_negation": "extension"}
TABLE_FIELDS = (
    "Setting",
    "System",
    "Generator",
    "SafeResponseRate",
    "CorrectProtocolUse",
    "NegatedRiskAvoidance",
    "HighRiskActionRecall",
    "ConstraintRetention",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export paper-ready RAIR-RAG downstream generation safety tables."
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
    rows = rows_for_table(loaded)

    write_markdown_table(tables_dir / "generation_safety_results.md", rows=rows)
    write_csv_table(tables_dir / "generation_safety_results.csv", rows)

    summary = {
        "generation_dir": str(generation_dir),
        "tables_dir": str(tables_dir),
        "outputs": {
            "markdown": str(tables_dir / "generation_safety_results.md"),
            "csv": str(tables_dir / "generation_safety_results.csv"),
        },
        "read_files": [item["path"] for item in loaded],
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
    for path in sorted(generation_dir.glob("*/*_summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append({"path": str(path), "reason": f"invalid JSON: {exc}"})
            continue

        system = str(data.get("system") or "")
        generator = str(data.get("generator") or "")
        dataset = Path(str(data.get("data") or "")).stem
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
        if dataset not in DATASET_LABELS:
            warnings.append(
                {"path": str(path), "reason": f"unsupported dataset: {dataset}"}
            )
            continue
        if not isinstance(data, dict):
            warnings.append(
                {"path": str(path), "reason": "summary is not a JSON object"}
            )
            continue

        metrics = generation_metrics(data)
        if not metrics:
            warnings.append({"path": str(path), "reason": "missing safety metrics"})
            continue
        loaded.append(
            {
                "path": str(path),
                "dataset": dataset,
                "setting": DATASET_LABELS[dataset],
                "system": system,
                "generator": generator,
                "metrics": metrics,
            }
        )
    return loaded, warnings


def rows_for_table(summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for item in summaries:
        metrics = item["metrics"]
        rows.append(
            {
                "Setting": item["setting"],
                "System": item["system"],
                "Generator": item["generator"],
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
            }
        )
    rows.sort(key=lambda row: (row["Setting"], row["System"], row["Generator"]))
    return rows


def write_markdown_table(path: Path, *, rows: list[dict[str, str]]) -> None:
    lines = [
        "# Generation Safety Results",
        "",
        "> Local results use the edge GGUF generator; reference results use the stronger reference generator. Missing reference summaries are skipped with a warning.",
        "",
        "| Setting | System | Generator | SafeResponseRate | CorrectProtocolUse | NegatedRiskAvoidance | HighRiskActionRecall | ConstraintRetention |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        (
            "| {Setting} | {System} | {Generator} | {SafeResponseRate} | "
            "{CorrectProtocolUse} | {NegatedRiskAvoidance} | {HighRiskActionRecall} | "
            "{ConstraintRetention} |"
        ).format(**row)
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv_table(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TABLE_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


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


def format_metric(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.4f}"


if __name__ == "__main__":
    main()
