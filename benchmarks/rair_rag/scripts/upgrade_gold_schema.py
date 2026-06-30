from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_schema import load_routing_cases
from runtime.risk_candidate import infer_evidence_type
from runtime.risk_confidence import confidence_for_term

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IN = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "gold" / "rair_gold_all.jsonl"
)
DEFAULT_OUT = (
    PROJECT_ROOT
    / "benchmarks"
    / "rair_rag"
    / "data"
    / "gold"
    / "rair_gold_all_v2.jsonl"
)
DEFAULT_WARNINGS = (
    PROJECT_ROOT / "build" / "rair_eval" / "schema_upgrade_warnings.jsonl"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade RAIR-RAG gold JSONL to structured risk_candidates."
    )
    parser.add_argument("--in", dest="input_path", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", dest="out_path", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--warnings", dest="warnings_path", type=Path, default=DEFAULT_WARNINGS
    )
    args = parser.parse_args()

    summary = upgrade_gold_schema(
        input_path=args.input_path,
        out_path=args.out_path,
        warnings_path=args.warnings_path,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def upgrade_gold_schema(
    input_path: Path = DEFAULT_IN,
    out_path: Path = DEFAULT_OUT,
    warnings_path: Path = DEFAULT_WARNINGS,
) -> dict[str, int]:
    input_path = input_path.resolve()
    out_path = out_path.resolve()
    warnings_path = warnings_path.resolve()
    if input_path == out_path:
        raise ValueError("refusing to overwrite input JSONL")

    upgraded_rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for lineno, line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        upgraded = upgrade_case(row, warnings=warnings, lineno=lineno)
        upgraded_rows.append(upgraded)

    write_jsonl(upgraded_rows, out_path)
    write_jsonl(warnings, warnings_path)
    load_routing_cases(out_path)
    return {
        "input_cases": len(upgraded_rows),
        "output_cases": len(upgraded_rows),
        "warnings": len(warnings),
        "with_risk_candidates": sum(
            1 for row in upgraded_rows if row.get("risk_candidates")
        ),
    }


def upgrade_case(
    row: dict[str, Any],
    warnings: list[dict[str, Any]],
    lineno: int,
) -> dict[str, Any]:
    upgraded = dict(row)
    should_not_trigger = list(upgraded.get("should_not_trigger") or [])
    if not upgraded.get("suppressed_protocols"):
        upgraded["suppressed_protocols"] = should_not_trigger
    if not upgraded.get("risk_candidates"):
        upgraded["risk_candidates"] = risk_candidates_from_mentions(
            upgraded, warnings=warnings, lineno=lineno
        )
    return upgraded


def risk_candidates_from_mentions(
    row: dict[str, Any],
    warnings: list[dict[str, Any]],
    lineno: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[int, int]]] = set()
    for mention in row.get("risk_mentions") or []:
        parsed = parse_risk_mention(str(mention), row, warnings=warnings, lineno=lineno)
        if parsed is None:
            continue
        key = (parsed["risk"], parsed["trigger"], tuple(parsed["span"]))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(parsed)
    return candidates


def parse_risk_mention(
    mention: str,
    row: dict[str, Any],
    warnings: list[dict[str, Any]],
    lineno: int,
) -> dict[str, Any] | None:
    if ":" not in mention:
        add_warning(row, warnings, lineno, mention, "missing_colon")
        return None

    label, trigger = [part.strip() for part in mention.split(":", 1)]
    if not label or not trigger:
        add_warning(row, warnings, lineno, mention, "empty_risk_or_trigger")
        return None

    if label == "inferred":
        risk = trigger
        trigger_text = str(row.get("raw_input") or row.get("canonical_input") or "")
        inferred = True
    else:
        risk = label
        trigger_text = trigger
        inferred = False

    if not risk or not trigger_text:
        add_warning(row, warnings, lineno, mention, "unresolved_risk_or_trigger")
        return None

    span = locate_trigger(
        trigger_text=trigger_text,
        row=row,
        mention=mention,
        warnings=warnings,
        lineno=lineno,
        warn_if_missing=not inferred,
    )
    return {
        "risk": risk,
        "trigger": trigger_text,
        "span": span,
        "confidence": confidence_for_term(trigger_text),
        "evidence_type": infer_evidence_type(risk, risk, trigger_text),
        "expected_negated": risk in set(row.get("negated_risks") or []),
    }


def locate_trigger(
    trigger_text: str,
    row: dict[str, Any],
    mention: str,
    warnings: list[dict[str, Any]],
    lineno: int,
    warn_if_missing: bool,
) -> list[int]:
    for field_name in ("raw_input", "canonical_input"):
        text = str(row.get(field_name) or "")
        start = text.find(trigger_text)
        if start >= 0:
            return [start, start + len(trigger_text)]
    if warn_if_missing:
        add_warning(row, warnings, lineno, mention, "trigger_not_found")
    return [-1, -1]


def add_warning(
    row: dict[str, Any],
    warnings: list[dict[str, Any]],
    lineno: int,
    mention: str,
    reason: str,
) -> None:
    warnings.append(
        {
            "line": lineno,
            "id": row.get("id"),
            "canonical_id": row.get("canonical_id"),
            "risk_mention": mention,
            "reason": reason,
        }
    )


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text((text + "\n") if text else "", encoding="utf-8")


if __name__ == "__main__":
    main()
