from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GENERATION_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"
DEFAULT_TABLES_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "tables"
SUPPORTED_GENERATORS = ("local-llm", "reference-llm")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export downstream generation latency tables."
    )
    parser.add_argument("--generation-dir", type=Path, default=DEFAULT_GENERATION_DIR)
    parser.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    summary_path = args.summary or (args.tables_dir / "generation_latency_summary.json")
    summary = export_generation_latency_tables(
        generation_dir=args.generation_dir,
        tables_dir=args.tables_dir,
        summary_path=summary_path,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def export_generation_latency_tables(
    *, generation_dir: Path, tables_dir: Path, summary_path: Path
) -> dict[str, Any]:
    tables_dir.mkdir(parents=True, exist_ok=True)
    rows, warnings = load_latency_rows(generation_dir)
    write_markdown_table(tables_dir / "generation_latency_results.md", rows=rows)
    write_csv_table(tables_dir / "generation_latency_results.csv", rows)
    summary = {
        "generation_dir": str(generation_dir),
        "tables_dir": str(tables_dir),
        "outputs": {
            "markdown": str(tables_dir / "generation_latency_results.md"),
            "csv": str(tables_dir / "generation_latency_results.csv"),
        },
        "warnings": warnings,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def load_latency_rows(
    generation_dir: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for path in sorted(generation_dir.glob("*/*_summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append({"path": str(path), "reason": f"invalid JSON: {exc}"})
            continue
        generator = str(data.get("generator") or "")
        if generator not in SUPPORTED_GENERATORS:
            warnings.append(
                {"path": str(path), "reason": f"unsupported generator: {generator}"}
            )
            continue
        latency = data.get("latency_summary") or {}
        if not isinstance(latency, dict) or not latency.get("count"):
            warnings.append({"path": str(path), "reason": "missing latency summary"})
            continue
        rows.append(
            {
                "Setting": _setting_from_path(path),
                "System": str(data.get("system") or ""),
                "Generator": str(data.get("generator_model") or generator),
                "Count": str(int(latency.get("count") or 0)),
                "AvgMs": _fmt(latency.get("avg_ms")),
                "P50Ms": _fmt(latency.get("p50_ms")),
                "P95Ms": _fmt(latency.get("p95_ms")),
                "MaxMs": _fmt(latency.get("max_ms")),
            }
        )
    rows.sort(key=lambda row: (row["Setting"], row["System"], row["Generator"]))
    return rows, warnings


def write_markdown_table(path: Path, *, rows: list[dict[str, str]]) -> None:
    lines = [
        "# Generation Latency Results",
        "",
        "| Setting | System | Generator | Count | AvgMs | P50Ms | P95Ms | MaxMs |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        "| {Setting} | {System} | {Generator} | {Count} | {AvgMs} | {P50Ms} | {P95Ms} | {MaxMs} |".format(
            **row
        )
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv_table(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "Setting",
        "System",
        "Generator",
        "Count",
        "AvgMs",
        "P50Ms",
        "P95Ms",
        "MaxMs",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _setting_from_path(path: Path) -> str:
    parent = path.parent.name
    if parent == "reference":
        return "Strong reference"
    return "Edge-local"


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.3f}"


if __name__ == "__main__":
    main()
