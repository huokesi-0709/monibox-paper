from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "qwen-plus"
DEFAULT_SETTING = "strong_hosted_reference"
DEFAULT_GENERATOR = "reference-llm"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize completed downstream generation JSONL outputs into a "
            "metadata-complete copy without modifying the original file."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--setting", default=DEFAULT_SETTING)
    parser.add_argument("--dedupe", action="store_true")
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()

    manifest = normalize_generation_outputs(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        setting=args.setting,
        dedupe=args.dedupe,
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"manifest": str(args.manifest_out), **manifest},
            ensure_ascii=False,
        )
    )


def normalize_generation_outputs(
    *,
    input_path: Path,
    output_path: Path,
    model: str,
    setting: str,
    dedupe: bool,
) -> dict[str, Any]:
    rows = _load_jsonl(input_path)
    normalized_rows = [
        _normalize_row(row, model=model, setting=setting) for row in rows
    ]
    duplicate_count = 0
    if dedupe:
        normalized_rows, duplicate_count = _dedupe_rows(normalized_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_path, normalized_rows)

    return {
        "input": str(input_path),
        "output": str(output_path),
        "generator": DEFAULT_GENERATOR,
        "model": model,
        "setting": setting,
        "dedupe": dedupe,
        "input_count": len(rows),
        "normalized_count": len(normalized_rows),
        "duplicate_count": duplicate_count,
        "systems": _systems(normalized_rows),
        "note": "No LLM was called; the original outputs JSONL was not modified.",
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                msg = f"{path} line {line_number} is not a JSON object"
                raise ValueError(msg)
            rows.append(payload)
    return rows


def _normalize_row(row: dict[str, Any], *, model: str, setting: str) -> dict[str, Any]:
    normalized = dict(row)
    original_model = normalized.get("model")
    if original_model not in (None, "", model):
        trace = normalized.get("trace")
        if not isinstance(trace, dict):
            trace = {"original_trace": trace} if trace is not None else {}
        trace = dict(trace)
        trace["original_model_name"] = original_model
        normalized["trace"] = trace

    normalized["generator"] = DEFAULT_GENERATOR
    normalized["model"] = model
    normalized["setting"] = setting
    return normalized


def _dedupe_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    selected: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str, str]] = []
    duplicate_count = 0

    for row in rows:
        key = _dedupe_key(row)
        if key not in selected:
            selected[key] = row
            order.append(key)
            continue
        duplicate_count += 1
        if _row_priority(row) > _row_priority(selected[key]):
            selected[key] = row

    return [selected[key] for key in order], duplicate_count


def _dedupe_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("id") or ""),
        str(row.get("system") or ""),
        str(row.get("generator") or ""),
        str(row.get("model") or ""),
    )


def _row_priority(row: dict[str, Any]) -> int:
    if row.get("status") == "ok":
        return 2
    if not row.get("error"):
        return 1
    return 0


def _systems(rows: list[dict[str, Any]]) -> list[str]:
    systems = {str(row.get("system")) for row in rows if row.get("system")}
    return sorted(systems)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
