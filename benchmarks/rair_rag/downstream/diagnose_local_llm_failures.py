from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GENERATION_DIR = (
    PROJECT_ROOT / "build" / "downstream_eval" / "generation" / "local"
)
DEFAULT_REPORT = DEFAULT_GENERATION_DIR / "local_llm_failure_report.md"
FAILURE_TYPES = (
    "model_load_error",
    "context_overflow",
    "empty_generation",
    "invalid_json",
    "runtime_exception",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose local-llm generation output failures without rerunning LLMs."
    )
    parser.add_argument("--generation-dir", type=Path, default=DEFAULT_GENERATION_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sample-limit", type=int, default=20)
    args = parser.parse_args()

    report = diagnose_local_llm_failures(
        generation_dir=args.generation_dir,
        out_path=args.out,
        sample_limit=args.sample_limit,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def diagnose_local_llm_failures(
    *, generation_dir: Path, out_path: Path, sample_limit: int = 20
) -> dict[str, Any]:
    output_paths = sorted(
        path
        for path in generation_dir.glob("*_outputs.jsonl")
        if "_evaluated" not in path.name
    )
    summaries = {
        path.name: _read_json(path)
        for path in sorted(generation_dir.glob("*_summary.json"))
        if "_evaluated" not in path.name
    }

    file_reports = []
    global_failure_types: Counter[str] = Counter()
    global_exception_types: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    for output_path in output_paths:
        rows = _read_jsonl(output_path)
        summary_name = output_path.name.replace("_outputs.jsonl", "_summary.json")
        file_report = _diagnose_rows(
            output_path=output_path,
            summary=summaries.get(summary_name, {}),
            rows=rows,
            sample_limit=max(0, sample_limit - len(samples)),
        )
        file_reports.append(file_report["summary"])
        global_failure_types.update(file_report["failure_types"])
        global_exception_types.update(file_report["exception_types"])
        samples.extend(file_report["samples"])

    report = {
        "generation_dir": str(generation_dir),
        "output_files": [str(path) for path in output_paths],
        "summary_files": [str(generation_dir / name) for name in sorted(summaries)],
        "failure_types": dict(global_failure_types),
        "exception_types": dict(global_exception_types),
        "files": file_reports,
        "sample_count": len(samples),
        "report": str(out_path),
    }
    write_markdown_report(out_path, report=report, samples=samples)
    return report


def _diagnose_rows(
    *,
    output_path: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    sample_limit: int,
) -> dict[str, Any]:
    failure_types: Counter[str] = Counter()
    exception_types: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    failed_cases = 0
    parse_failed_cases = 0
    empty_output_cases = 0

    for row in rows:
        status_failed = row.get("status") == "failed"
        parse_failed = _parse_failed(row)
        empty_output = _empty_output(row)
        error = str(row.get("error") or "")
        if status_failed:
            failed_cases += 1
            exception_types[_exception_type(error)] += 1
        if parse_failed:
            parse_failed_cases += 1
        if empty_output:
            empty_output_cases += 1

        failure_type = _failure_type(row)
        if failure_type:
            failure_types[failure_type] += 1
            if len(samples) < sample_limit:
                samples.append(_sample_row(output_path, row, failure_type))

    summary_failed = _int_value(
        summary.get("failed_cases")
        if "failed_cases" in summary
        else summary.get("num_failures")
    )
    file_summary = {
        "output": str(output_path),
        "summary_failed_cases": summary_failed,
        "row_count": len(rows),
        "failed_cases": failed_cases,
        "parse_failed_cases": parse_failed_cases,
        "empty_output_cases": empty_output_cases,
        "exception_types": dict(exception_types),
        "failure_types": dict(failure_types),
    }
    return {
        "summary": file_summary,
        "failure_types": failure_types,
        "exception_types": exception_types,
        "samples": samples,
    }


def _failure_type(row: dict[str, Any]) -> str:
    error = str(row.get("error") or "")
    parse_error = str((_parsed_output(row).get("_parse_error") or ""))
    raw_output = str(row.get("raw_output") or "")
    text = " ".join([error, parse_error]).lower()
    if "gguf" in text or "model file not found" in text or "load model" in text:
        return "model_load_error"
    if "context" in text and ("overflow" in text or "exceed" in text or "n_ctx" in text):
        return "context_overflow"
    if "llama-cpp-python is not installed" in text:
        return "runtime_exception"
    if row.get("status") == "failed" or error:
        return "runtime_exception"
    if not raw_output.strip():
        return "empty_generation"
    if _parse_failed(row):
        return "invalid_json"
    return ""


def _sample_row(output_path: Path, row: dict[str, Any], failure_type: str) -> dict[str, Any]:
    return {
        "file": str(output_path),
        "id": row.get("id"),
        "system": row.get("system"),
        "failure_type": failure_type,
        "status": row.get("status"),
        "error": row.get("error"),
        "parse_error": _parsed_output(row).get("_parse_error"),
        "raw_output_preview": str(row.get("raw_output") or "")[:300],
        "prompt_length": len(str(row.get("prompt") or "")),
        "retrieved_evidence_count": len(_list_value(row.get("retrieved_evidence"))),
    }


def write_markdown_report(
    path: Path, *, report: dict[str, Any], samples: list[dict[str, Any]]
) -> None:
    lines = [
        "# Local LLM Failure Report",
        "",
        f"- Generation directory: `{report['generation_dir']}`",
        f"- Output files: {len(report['output_files'])}",
        f"- Sample failures shown: {len(samples)}",
        "",
        "## Failure Type Counts",
        "",
        "| FailureType | Count |",
        "|---|---:|",
    ]
    for failure_type in FAILURE_TYPES:
        lines.append(f"| {failure_type} | {report['failure_types'].get(failure_type, 0)} |")
    lines.extend(["", "## Exception Types", "", "| ExceptionType | Count |", "|---|---:|"])
    exception_types = report.get("exception_types") or {}
    if exception_types:
        for name, count in sorted(exception_types.items()):
            lines.append(f"| {_escape(name)} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Files",
            "",
            "| Output | Rows | SummaryFailedCases | FailedCases | ParseFailedCases | EmptyOutputCases |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in report["files"]:
        lines.append(
            "| {output} | {row_count} | {summary_failed_cases} | {failed_cases} | "
            "{parse_failed_cases} | {empty_output_cases} |".format(
                output=_escape(item["output"]),
                row_count=item["row_count"],
                summary_failed_cases=item["summary_failed_cases"],
                failed_cases=item["failed_cases"],
                parse_failed_cases=item["parse_failed_cases"],
                empty_output_cases=item["empty_output_cases"],
            )
        )

    lines.extend(
        [
            "",
            "## First Failure Samples",
            "",
            "| # | File | ID | System | FailureType | Status | Error | ParseError | RawOutputPreview | PromptLength | RetrievedEvidenceCount |",
            "|---:|---|---|---|---|---|---|---|---|---:|---:|",
        ]
    )
    if samples:
        for index, sample in enumerate(samples, start=1):
            lines.append(
                "| {index} | {file} | {id} | {system} | {failure_type} | {status} | "
                "{error} | {parse_error} | {raw_output_preview} | {prompt_length} | "
                "{retrieved_evidence_count} |".format(
                    index=index,
                    file=_escape(sample["file"]),
                    id=_escape(sample["id"]),
                    system=_escape(sample["system"]),
                    failure_type=_escape(sample["failure_type"]),
                    status=_escape(sample["status"]),
                    error=_escape(sample["error"]),
                    parse_error=_escape(sample["parse_error"]),
                    raw_output_preview=_escape(sample["raw_output_preview"]),
                    prompt_length=sample["prompt_length"],
                    retrieved_evidence_count=sample["retrieved_evidence_count"],
                )
            )
    else:
        lines.append("|  |  |  |  |  |  |  |  |  |  |  |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            rows.append(
                {
                    "status": "failed",
                    "error": "JSONDecodeError: output row is not valid JSON",
                    "raw_output": line,
                }
            )
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _parse_failed(row: dict[str, Any]) -> bool:
    parsed = _parsed_output(row)
    if "_parse_ok" in parsed:
        return not bool(parsed.get("_parse_ok"))
    trace = row.get("trace")
    if isinstance(trace, dict) and "parse_ok" in trace:
        return not bool(trace.get("parse_ok"))
    return False


def _empty_output(row: dict[str, Any]) -> bool:
    return not str(row.get("raw_output") or "").strip()


def _parsed_output(row: dict[str, Any]) -> dict[str, Any]:
    parsed = row.get("parsed_output")
    return parsed if isinstance(parsed, dict) else {}


def _exception_type(error: str) -> str:
    if not error:
        return "none"
    return error.split(":", 1)[0].strip() or "unknown"


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
