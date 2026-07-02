from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RETRIEVAL_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "retrieval"
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "build"
    / "downstream_eval"
    / "tables"
    / "retrieval_check_report.md"
)
REQUIRED_SYSTEMS = ("vanilla-rag", "keyword-rag", "bert-rag", "rair-rag")
METRIC_FIELDS = (
    "ProtocolAcc",
    "EvidenceHit@1",
    "EvidenceHit@3",
    "PFTR",
    "HRR",
)
OLD_BERT_PROXY_MARKERS = (
    "bert-multilabel local proxy",
    "candidate-multilabel local proxy",
)
BERT_PROXY_WARNING = (
    "BERT-RAG must be rerun after real BERT baseline is trained."
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check downstream retrieval outputs without running experiments."
    )
    parser.add_argument("--retrieval-dir", type=Path, default=DEFAULT_RETRIEVAL_DIR)
    parser.add_argument("--dataset", default="rair_test")
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    report = check_retrieval_outputs(
        retrieval_dir=args.retrieval_dir,
        dataset=args.dataset,
        out_path=args.out,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def check_retrieval_outputs(
    *, retrieval_dir: Path, dataset: str, out_path: Path
) -> dict[str, Any]:
    rows = []
    warnings = []
    for system in REQUIRED_SYSTEMS:
        summary_path = retrieval_dir / f"{dataset}_{system}_summary.json"
        prediction_path = retrieval_dir / f"{dataset}_{system}_predictions.jsonl"
        if not summary_path.exists():
            rows.append(_missing_row(system=system, summary_path=summary_path))
            warnings.append(f"missing summary for {system}: {summary_path}")
            continue

        summary = _read_json(summary_path)
        row = _row_from_summary(
            system=system,
            summary=summary,
            summary_path=summary_path,
        )
        if system == "bert-rag" and _bert_rag_uses_old_proxy(summary, prediction_path):
            row["Status"] = "WARN"
            row["Notes"] = BERT_PROXY_WARNING
            warnings.append(BERT_PROXY_WARNING)
        rows.append(row)

    write_markdown_report(
        out_path,
        dataset=dataset,
        retrieval_dir=retrieval_dir,
        rows=rows,
        warnings=warnings,
    )
    return {
        "retrieval_dir": str(retrieval_dir),
        "dataset": dataset,
        "report": str(out_path),
        "required_systems": list(REQUIRED_SYSTEMS),
        "rows": rows,
        "warnings": warnings,
    }


def write_markdown_report(
    path: Path,
    *,
    dataset: str,
    retrieval_dir: Path,
    rows: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    lines = [
        "# Downstream Retrieval Check Report",
        "",
        f"- Dataset: `{dataset}`",
        f"- Retrieval directory: `{retrieval_dir}`",
        "",
        "| System | Status | NumCases | ProtocolAcc | EvidenceHit@1 | EvidenceHit@3 | PFTR | HRR | Summary | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {System} | {Status} | {NumCases} | {ProtocolAcc} | {EvidenceHit@1} | "
            "{EvidenceHit@3} | {PFTR} | {HRR} | {Summary} | {Notes} |".format(
                **row
            )
        )
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in dict.fromkeys(warnings))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _row_from_summary(
    *, system: str, summary: dict[str, Any], summary_path: Path
) -> dict[str, str]:
    metrics = summary.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    return {
        "System": system,
        "Status": "OK",
        "NumCases": _format_int(summary.get("num_cases") or metrics.get("num_cases")),
        "ProtocolAcc": _format_float(metrics.get("ProtocolAcc")),
        "EvidenceHit@1": _format_float(metrics.get("EvidenceHit@1")),
        "EvidenceHit@3": _format_float(metrics.get("EvidenceHit@3")),
        "PFTR": _format_float(metrics.get("PFTR")),
        "HRR": _format_float(metrics.get("HRR")),
        "Summary": str(summary_path),
        "Notes": "",
    }


def _missing_row(*, system: str, summary_path: Path) -> dict[str, str]:
    return {
        "System": system,
        "Status": "MISSING",
        "NumCases": "",
        "ProtocolAcc": "",
        "EvidenceHit@1": "",
        "EvidenceHit@3": "",
        "PFTR": "",
        "HRR": "",
        "Summary": str(summary_path),
        "Notes": "summary not found",
    }


def _bert_rag_uses_old_proxy(summary: dict[str, Any], prediction_path: Path) -> bool:
    marker = _first_marker(json.dumps(summary, ensure_ascii=False))
    if marker:
        return True
    if not prediction_path.exists():
        return False
    try:
        with prediction_path.open("r", encoding="utf-8-sig") as handle:
            for index, line in enumerate(handle):
                marker = _first_marker(line)
                if marker:
                    return True
                if index >= 49:
                    break
    except UnicodeDecodeError:
        return False
    return False


def _first_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in OLD_BERT_PROXY_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def _format_float(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def _format_int(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return ""


if __name__ == "__main__":
    main()
