from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.downstream.llm_clients import (
    DEFAULT_REFERENCE_BASE_URL,
    DEFAULT_REFERENCE_MODEL,
    DEFAULT_REFERENCE_PROVIDER,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
)
DEFAULT_REFERENCE_DIR = (
    PROJECT_ROOT / "build" / "downstream_eval" / "generation" / "reference"
)
DEFAULT_SYSTEMS = ("vanilla-rag", "rair-rag")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill metadata for completed downstream generation outputs."
    )
    parser.add_argument("--generation-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    parser.add_argument("--generator", default="reference-llm")
    parser.add_argument("--model", default=DEFAULT_REFERENCE_MODEL)
    parser.add_argument("--provider", default=DEFAULT_REFERENCE_PROVIDER)
    parser.add_argument("--base-url", default=DEFAULT_REFERENCE_BASE_URL)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--topk", type=int, default=3)
    args = parser.parse_args()

    summary = backfill_generation_metadata(
        generation_dir=args.generation_dir,
        generator=args.generator,
        model=args.model,
        provider=args.provider,
        base_url=args.base_url,
        data_path=args.data,
        topk=args.topk,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def backfill_generation_metadata(
    *,
    generation_dir: Path,
    generator: str,
    model: str,
    provider: str,
    base_url: str,
    data_path: Path,
    topk: int,
) -> dict[str, Any]:
    generation_dir.mkdir(parents=True, exist_ok=True)
    output_summaries: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    for output_path in sorted(generation_dir.glob("*_outputs.jsonl")):
        rows, load_warning = _load_jsonl(output_path)
        if load_warning:
            warnings.append({"path": str(output_path), "reason": load_warning})
            continue
        if not rows:
            warnings.append({"path": str(output_path), "reason": "empty output file"})
            continue

        row_generator = str(rows[0].get("generator") or generator)
        if row_generator != generator:
            warnings.append(
                {
                    "path": str(output_path),
                    "reason": f"skipped generator {row_generator}",
                }
            )
            continue

        changed = _backfill_rows(
            rows=rows,
            generator=generator,
            model=model,
            provider=provider,
            base_url=base_url,
        )
        if changed:
            _write_jsonl(output_path, rows)

        summary_path = output_path.with_name(
            output_path.name.replace("_outputs.jsonl", "_summary.json")
        )
        output_summary = _write_backfilled_summary(
            summary_path=summary_path,
            rows=rows,
            output_path=output_path,
            generator=generator,
            model=model,
            provider=provider,
            base_url=base_url,
            data_path=data_path,
            topk=topk,
        )
        output_summaries.append(output_summary)

    manifest = {
        "generator": generator,
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "data": str(data_path),
        "systems": list(DEFAULT_SYSTEMS),
        "topk": topk,
        "created_from_existing_outputs": True,
        "outputs": output_summaries,
        "note": (
            "The original output files did not include complete model metadata "
            "or per-sample latency. Metadata was backfilled from the completed "
            "qwen-plus reference run configuration; missing latency values are "
            "left as null and summarized as not recorded."
        ),
    }
    manifest_path = generation_dir / "reference_generation_manifest.json"
    _write_json(manifest_path, manifest)

    return {
        "generation_dir": str(generation_dir),
        "manifest": str(manifest_path),
        "outputs": output_summaries,
        "warnings": warnings,
    }


def _backfill_rows(
    *,
    rows: list[dict[str, Any]],
    generator: str,
    model: str,
    provider: str,
    base_url: str,
) -> bool:
    changed = False
    for row in rows:
        changed |= _set_if_missing(row, "generator", generator)
        changed |= _set_if_missing(row, "generator_model", model)
        changed |= _set_if_missing(row, "generator_provider", provider)
        changed |= _set_if_missing(row, "generator_base_url", base_url)
        if "latency_ms" not in row:
            row["latency_ms"] = None
            row["latency_source"] = "not_recorded_in_original_run"
            changed = True
    return changed


def _write_backfilled_summary(
    *,
    summary_path: Path,
    rows: list[dict[str, Any]],
    output_path: Path,
    generator: str,
    model: str,
    provider: str,
    base_url: str,
    data_path: Path,
    topk: int,
) -> dict[str, Any]:
    summary = _load_json(summary_path)
    if not summary:
        summary = {}
    for transient_key in (
        "avg_latency_ms",
        "case_end",
        "case_start",
        "completed_cases",
        "failed_cases",
        "num_generated",
        "num_skipped_existing",
        "p95_latency_ms",
        "resume",
        "skip_existing",
        "skipped_cases",
    ):
        summary.pop(transient_key, None)
    summary.update(
        {
            "data": str(summary.get("data") or data_path),
            "system": str(summary.get("system") or _system_from_name(output_path.name)),
            "generator": generator,
            "generator_model": model,
            "generator_provider": provider,
            "generator_base_url": base_url,
            "topk": int(summary.get("topk") or topk),
            "num_cases": len(rows),
            "num_outputs": len(rows),
            "num_failures": sum(1 for row in rows if row.get("error")),
            "latency_summary": _latency_summary(rows),
            "output": str(output_path),
            "metadata_backfilled": True,
            "created_from_existing_outputs": True,
        }
    )
    _write_json(summary_path, summary)
    return {
        "summary": str(summary_path),
        "output": str(output_path),
        "system": summary.get("system"),
        "num_outputs": summary.get("num_outputs"),
        "num_failures": summary.get("num_failures"),
        "latency_summary": summary.get("latency_summary"),
    }


def _latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    missing = 0
    for row in rows:
        value = row.get("latency_ms")
        if value is None:
            missing += 1
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            missing += 1
    if not values:
        return {
            "count": 0,
            "missing_count": missing,
            "note": "latency_ms was not recorded in the original completed run.",
        }
    values.sort()
    count = len(values)
    return {
        "count": count,
        "missing_count": missing,
        "avg_ms": round(sum(values) / count, 3),
        "p50_ms": round(values[int((count - 1) * 0.5)], 3),
        "p95_ms": round(values[int((count - 1) * 0.95)], 3),
        "max_ms": round(values[-1], 3),
    }


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return rows, str(exc)
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            return rows, f"invalid JSONL at line {index}: {exc}"
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _set_if_missing(row: dict[str, Any], key: str, value: Any) -> bool:
    if row.get(key) in (None, ""):
        row[key] = value
        return True
    return False


def _system_from_name(name: str) -> str:
    for system in DEFAULT_SYSTEMS:
        if f"_{system}_" in name:
            return system
    return ""


if __name__ == "__main__":
    main()
