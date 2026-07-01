from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RETRIEVAL_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "retrieval"
DEFAULT_TABLES_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "tables"
SUPPORTED_SYSTEMS = ("vanilla-rag", "keyword-rag", "bert-rag", "rair-rag")
MAIN_DATASET = "rair_test"
EXTENSION_DATASET = "rair_test_multi_intent_negation"
TABLE_FIELDS = (
    "System",
    "ProtocolAcc",
    "HRR",
    "PFTR",
    "EvidenceHit@1",
    "EvidenceHit@3",
    "NumCases",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export paper-ready RAIR-RAG downstream retrieval tables."
    )
    parser.add_argument("--retrieval-dir", type=Path, default=DEFAULT_RETRIEVAL_DIR)
    parser.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    summary_path = args.summary or (
        args.tables_dir / "retrieval_table_export_summary.json"
    )
    summary = export_downstream_tables(
        retrieval_dir=args.retrieval_dir,
        tables_dir=args.tables_dir,
        summary_path=summary_path,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def export_downstream_tables(
    *, retrieval_dir: Path, tables_dir: Path, summary_path: Path
) -> dict[str, Any]:
    tables_dir.mkdir(parents=True, exist_ok=True)
    loaded, skipped = load_retrieval_summaries(retrieval_dir)

    main_rows = rows_for_dataset(loaded, MAIN_DATASET)
    extension_rows = rows_for_dataset(loaded, EXTENSION_DATASET)

    write_markdown_table(
        tables_dir / "retrieval_main_results.md",
        title="Table A. Main Test Set Downstream Retrieval Results",
        rows=main_rows,
    )
    write_csv_table(tables_dir / "retrieval_main_results.csv", main_rows)
    write_markdown_table(
        tables_dir / "retrieval_extension_results.md",
        title=(
            "Table B. Composite Perturbation Extension Stress Test Results "
            "(not the core consensus-gold main metric)"
        ),
        rows=extension_rows,
        note=(
            "This table reports the multi-intent + negation extension stress test; "
            "it should not be interpreted as the core gold main-test metric."
        ),
    )
    write_csv_table(tables_dir / "retrieval_extension_results.csv", extension_rows)

    summary = {
        "retrieval_dir": str(retrieval_dir),
        "tables_dir": str(tables_dir),
        "outputs": {
            "main_markdown": str(tables_dir / "retrieval_main_results.md"),
            "main_csv": str(tables_dir / "retrieval_main_results.csv"),
            "extension_markdown": str(tables_dir / "retrieval_extension_results.md"),
            "extension_csv": str(tables_dir / "retrieval_extension_results.csv"),
        },
        "read_files": [item["path"] for item in loaded],
        "skipped_files": skipped,
        "included_systems": list(SUPPORTED_SYSTEMS),
        "datasets": {"main": MAIN_DATASET, "extension_stress_test": EXTENSION_DATASET},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def load_retrieval_summaries(
    retrieval_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    loaded: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for path in sorted(retrieval_dir.glob("*_summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            skipped.append({"path": str(path), "reason": f"invalid JSON: {exc}"})
            continue

        system = str(data.get("system") or "")
        dataset = dataset_name_from_summary(data)
        metrics = data.get("metrics")
        if system not in SUPPORTED_SYSTEMS:
            skipped.append(
                {"path": str(path), "reason": f"unsupported system: {system}"}
            )
            continue
        if dataset not in {MAIN_DATASET, EXTENSION_DATASET}:
            skipped.append(
                {"path": str(path), "reason": f"unsupported dataset: {dataset}"}
            )
            continue
        if not isinstance(metrics, dict):
            skipped.append({"path": str(path), "reason": "missing metrics object"})
            continue

        loaded.append(
            {
                "path": str(path),
                "dataset": dataset,
                "system": system,
                "num_cases": int(
                    data.get("num_cases") or metrics.get("num_cases") or 0
                ),
                "metrics": metrics,
            }
        )
    return loaded, skipped


def rows_for_dataset(
    summaries: list[dict[str, Any]], dataset: str
) -> list[dict[str, str]]:
    by_system = {
        str(item["system"]): item
        for item in summaries
        if item.get("dataset") == dataset
    }
    rows: list[dict[str, str]] = []
    for system in SUPPORTED_SYSTEMS:
        item = by_system.get(system)
        if item is None:
            rows.append(empty_row(system))
            continue
        metrics = item["metrics"]
        rows.append(
            {
                "System": system,
                "ProtocolAcc": format_metric(metrics.get("ProtocolAcc")),
                "HRR": format_metric(metrics.get("HRR")),
                "PFTR": format_metric(metrics.get("PFTR")),
                "EvidenceHit@1": format_metric(metrics.get("EvidenceHit@1")),
                "EvidenceHit@3": format_metric(metrics.get("EvidenceHit@3")),
                "NumCases": str(item["num_cases"]),
            }
        )
    return rows


def write_markdown_table(
    path: Path, *, title: str, rows: list[dict[str, str]], note: str = ""
) -> None:
    lines = [f"# {title}", ""]
    if note:
        lines.extend([f"> {note}", ""])
    lines.extend(
        [
            "| System | ProtocolAcc | HRR | PFTR | EvidenceHit@1 | EvidenceHit@3 | NumCases |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        (
            "| {System} | {ProtocolAcc} | {HRR} | {PFTR} | "
            "{EvidenceHit@1} | {EvidenceHit@3} | {NumCases} |"
        ).format(**row)
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv_table(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TABLE_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def dataset_name_from_summary(summary: dict[str, Any]) -> str:
    data_path = str(summary.get("data") or "")
    if data_path:
        return Path(data_path).stem
    return ""


def empty_row(system: str) -> dict[str, str]:
    return {
        "System": system,
        "ProtocolAcc": "",
        "HRR": "",
        "PFTR": "",
        "EvidenceHit@1": "",
        "EvidenceHit@3": "",
        "NumCases": "",
    }


def format_metric(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.4f}"


if __name__ == "__main__":
    main()
