from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = PROJECT_ROOT / "build" / "paper_readiness_report.md"
FORBIDDEN_MARKERS = (
    "".join(("Qwen", "2.5", "-7B-Instruct")),
    "".join(("qwen", "2.5", "-7b-instruct")),
    " ".join(("BERT-MultiLabel", "proxy")),
)
TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".csv",
    ".env",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    ".npm-cache",
}
SKIP_FILES = {"paper_readiness_report.md"}
MAX_SCAN_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class CheckResult:
    status: str
    item: str
    detail: str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check whether paper experiment artifacts are ready."
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = check_paper_readiness(root=args.root, out_path=args.out)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def check_paper_readiness(*, root: Path, out_path: Path) -> dict[str, Any]:
    results: list[CheckResult] = []
    marker_hits = scan_for_forbidden_markers(root)
    if marker_hits:
        detail = "; ".join(
            f"{hit['marker']} in {hit['path']}:{hit['line']}" for hit in marker_hits[:20]
        )
        if len(marker_hits) > 20:
            detail += f"; ... {len(marker_hits) - 20} more"
        results.append(CheckResult("FAIL", "Forbidden legacy strings", detail))
    else:
        results.append(
            CheckResult(
                "PASS",
                "Forbidden legacy strings",
                "No legacy Qwen marker or BERT proxy marker found in text files.",
            )
        )

    required_checks = [
        (
            "qwen-plus reference manifest",
            root / "build/downstream_eval/generation/reference/reference_generation_manifest.json",
            "FAIL",
            _qwen_manifest_detail,
        ),
        (
            "Reference generation vanilla outputs",
            root / "build/downstream_eval/generation/reference/rair_test_vanilla-rag_reference-llm_outputs.jsonl",
            "FAIL",
            _jsonl_count_detail,
        ),
        (
            "Reference generation RAIR outputs",
            root / "build/downstream_eval/generation/reference/rair_test_rair-rag_reference-llm_outputs.jsonl",
            "FAIL",
            _jsonl_count_detail,
        ),
        (
            "Local generation vanilla outputs",
            root / "build/downstream_eval/generation/local/rair_test_vanilla-rag_local-llm_outputs.jsonl",
            "WARN",
            _jsonl_count_detail,
        ),
        (
            "Local generation RAIR outputs",
            root / "build/downstream_eval/generation/local/rair_test_rair-rag_local-llm_outputs.jsonl",
            "WARN",
            _jsonl_count_detail,
        ),
        (
            "Generation safety table",
            root / "build/downstream_eval/tables/generation_safety_results.md",
            "FAIL",
            _file_size_detail,
        ),
        (
            "Generation latency table",
            root / "build/downstream_eval/tables/generation_latency_results.md",
            "FAIL",
            _file_size_detail,
        ),
        (
            "Retrieval main table",
            root / "build/downstream_eval/tables/retrieval_main_results.md",
            "FAIL",
            _file_size_detail,
        ),
        (
            "Real BERT test summary",
            root / "build/bert_multilabel/test_summary.json",
            "FAIL",
            _bert_summary_detail,
        ),
        (
            "Policy parameter table",
            root / "build/rair_eval/tables/policy_parameters.md",
            "FAIL",
            _file_size_detail,
        ),
        (
            "Negation failure analysis",
            root / "build/rair_eval/error_analysis/negation_failures.md",
            "FAIL",
            _file_size_detail,
        ),
    ]
    for item, path, missing_status, detail_fn in required_checks:
        results.append(check_required_file(item, path, missing_status, detail_fn))

    status_counts = {
        "PASS": sum(1 for result in results if result.status == "PASS"),
        "WARN": sum(1 for result in results if result.status == "WARN"),
        "FAIL": sum(1 for result in results if result.status == "FAIL"),
    }
    overall = "FAIL" if status_counts["FAIL"] else "WARN" if status_counts["WARN"] else "PASS"
    write_report(out_path, overall=overall, results=results, status_counts=status_counts)
    return {
        "overall": overall,
        "report": str(out_path),
        "status_counts": status_counts,
        "results": [result.__dict__ for result in results],
    }


def check_required_file(
    item: str,
    path: Path,
    missing_status: str,
    detail_fn: Any,
) -> CheckResult:
    if not path.exists():
        return CheckResult(missing_status, item, f"Missing: {path}")
    try:
        status, detail = detail_fn(path)
    except Exception as exc:
        return CheckResult("FAIL", item, f"Unreadable or invalid: {path}; {exc}")
    return CheckResult(status, item, detail)


def scan_for_forbidden_markers(root: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in iter_text_files(root):
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                for line_no, line in enumerate(handle, start=1):
                    for marker in FORBIDDEN_MARKERS:
                        if marker in line:
                            hits.append(
                                {
                                    "path": str(path),
                                    "line": line_no,
                                    "marker": marker,
                                }
                            )
        except (OSError, UnicodeDecodeError):
            continue
    return hits


def iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size > MAX_SCAN_BYTES:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {".env.example"}:
            files.append(path)
    return files


def write_report(
    path: Path,
    *,
    overall: str,
    results: list[CheckResult],
    status_counts: dict[str, int],
) -> None:
    lines = [
        "# Paper Readiness Report",
        "",
        f"- Overall: **{overall}**",
        f"- PASS: {status_counts['PASS']}",
        f"- WARN: {status_counts['WARN']}",
        f"- FAIL: {status_counts['FAIL']}",
        "",
        "| Status | Check | Detail |",
        "|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| {result.status} | {_escape(result.item)} | {_escape(result.detail)} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _qwen_manifest_detail(path: Path) -> tuple[str, str]:
    data = _read_json(path)
    model = str(data.get("model") or "")
    if model != "qwen-plus":
        return "FAIL", f"Manifest model is {model!r}, expected 'qwen-plus': {path}"
    outputs = data.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        return "WARN", f"Manifest exists but does not list outputs: {path}"
    return "PASS", f"qwen-plus manifest present with {len(outputs)} outputs: {path}"


def _bert_summary_detail(path: Path) -> tuple[str, str]:
    data = _read_json(path)
    model = str(data.get("model") or data.get("model_name") or "")
    method = str(data.get("method") or "")
    if "bert" not in model.lower() and "bert" not in method.lower():
        return "FAIL", f"Summary exists but does not identify a BERT model: {path}"
    return "PASS", f"Real BERT summary present: {path}"


def _jsonl_count_detail(path: Path) -> tuple[str, str]:
    count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                count += 1
    if count == 0:
        return "FAIL", f"File exists but has no rows: {path}"
    return "PASS", f"{count} rows: {path}"


def _file_size_detail(path: Path) -> tuple[str, str]:
    size = path.stat().st_size
    if size <= 0:
        return "FAIL", f"File exists but is empty: {path}"
    return "PASS", f"{size} bytes: {path}"


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
