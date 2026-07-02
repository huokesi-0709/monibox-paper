from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from app.config import settings
from benchmarks.rair_rag.downstream.llm_clients import (
    BaseGenerator,
    DEFAULT_LOCAL_MODEL_PATH,
    DEFAULT_REFERENCE_BASE_URL,
    DEFAULT_REFERENCE_MODEL,
    DEFAULT_REFERENCE_PROVIDER,
    LocalLlamaCppGenerator,
    ReferenceApiGenerator,
)
from benchmarks.rair_rag.downstream.prompt_builders import (
    build_rair_generation_prompt,
    build_vanilla_generation_prompt,
)
from benchmarks.rair_rag.downstream.retrieval_eval import load_downstream_cases
from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence
from benchmarks.rair_rag.downstream.systems import (
    DownstreamSystem,
    RairRagSystem,
    VanillaRagSystem,
)
from runtime.rag_engine import RagEngine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
)
DEFAULT_GENERATION_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"
SUPPORTED_SYSTEMS = {"vanilla-rag": VanillaRagSystem, "rair-rag": RairRagSystem}
SUPPORTED_GENERATORS = {"local-llm", "reference-llm"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run downstream generation evaluation with local or reference generators."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--system", choices=sorted(SUPPORTED_SYSTEMS), required=True)
    parser.add_argument(
        "--generator", choices=sorted(SUPPORTED_GENERATORS), required=True
    )
    parser.add_argument("--rag-db", type=Path, default=_default_rag_db_path())
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--sleep-between-calls", type=float, default=0.0)
    parser.add_argument("--case-start", type=int)
    parser.add_argument("--case-end", type=int)
    args = parser.parse_args()

    out_path = args.out or _default_out_path(args.data, args.system, args.generator)
    summary_path = args.summary or _default_summary_path(
        args.data, args.system, args.generator
    )
    try:
        summary = run_generation_eval(
            data_path=args.data,
            system_name=args.system,
            generator_name=args.generator,
            rag_db_path=args.rag_db,
            topk=args.topk,
            out_path=out_path,
            summary_path=summary_path,
            max_cases=args.max_cases,
            resume=args.resume,
            skip_existing=args.skip_existing,
            overwrite=args.overwrite,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            sleep_between_calls=args.sleep_between_calls,
            case_start=args.case_start,
            case_end=args.case_end,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_generation_eval(
    *,
    data_path: Path,
    system_name: str,
    generator_name: str,
    rag_db_path: Path,
    topk: int,
    out_path: Path,
    summary_path: Path,
    max_cases: int | None = None,
    generator: BaseGenerator | None = None,
    resume: bool = False,
    skip_existing: bool = False,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    sleep_between_calls: float = 0.0,
    case_start: int | None = None,
    case_end: int | None = None,
) -> dict[str, Any]:
    if topk <= 0:
        msg = "--topk must be a positive integer"
        raise ValueError(msg)
    if max_cases is not None and max_cases <= 0:
        msg = "--max-cases must be a positive integer when provided"
        raise ValueError(msg)
    if sleep_between_calls < 0:
        msg = "--sleep-between-calls must be non-negative"
        raise ValueError(msg)
    if timeout_seconds is not None and timeout_seconds <= 0:
        msg = "--timeout-seconds must be positive when provided"
        raise ValueError(msg)
    if max_retries is not None and max_retries < 0:
        msg = "--max-retries must be non-negative when provided"
        raise ValueError(msg)
    if overwrite and (resume or skip_existing):
        msg = "--overwrite cannot be combined with --resume or --skip-existing"
        raise ValueError(msg)
    if case_start is not None and case_start < 0:
        msg = "--case-start must be non-negative when provided"
        raise ValueError(msg)
    if case_end is not None and case_end < 0:
        msg = "--case-end must be non-negative when provided"
        raise ValueError(msg)
    if case_start is not None and case_end is not None and case_end < case_start:
        msg = "--case-end must be greater than or equal to --case-start"
        raise ValueError(msg)
    if system_name not in SUPPORTED_SYSTEMS:
        allowed = ", ".join(sorted(SUPPORTED_SYSTEMS))
        msg = f"unsupported system {system_name}; choose one of {allowed}"
        raise ValueError(msg)
    if generator_name not in SUPPORTED_GENERATORS:
        allowed = ", ".join(sorted(SUPPORTED_GENERATORS))
        msg = f"unsupported generator {generator_name}; choose one of {allowed}"
        raise ValueError(msg)
    if not rag_db_path.exists():
        msg = (
            f"RAG database not found: {rag_db_path}. "
            "Please run `uv run monibox-build-rag` first, or pass --rag-db / set "
            "RAG_DB_PATH to an existing rag.db file."
        )
        raise FileNotFoundError(msg)
    _prepare_output_path(out_path, overwrite=overwrite, resumable=resume or skip_existing)

    cases = load_downstream_cases(data_path)
    cases = cases[case_start:case_end]
    if max_cases is not None:
        cases = cases[:max_cases]

    system = SUPPORTED_SYSTEMS[system_name]()
    rag_engine = RagEngine(str(rag_db_path))
    active_generator = generator
    runtime_meta = (
        _generator_runtime_metadata(active_generator, generator_name)
        if active_generator is not None
        else _default_runtime_metadata(generator_name)
    )
    dataset = data_path.stem
    should_skip_existing = bool(resume or skip_existing)
    existing_by_id = (
        _load_completed_rows_by_id(out_path) if should_skip_existing else {}
    )
    completed_cases = 0
    failed_cases = 0
    skipped_cases = 0
    latencies_ms: list[float] = []
    for case in cases:
        case_id = str(case.id)
        existing = existing_by_id.get(case_id)
        if existing is not None:
            skipped_cases += 1
            completed_cases += 1
            existing_latency = _coerce_latency_ms(existing.get("latency_ms"))
            if existing_latency is not None:
                latencies_ms.append(existing_latency)
            continue
        if active_generator is None:
            active_generator = build_generator(
                generator_name,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            runtime_meta = _generator_runtime_metadata(active_generator, generator_name)
        started = time.perf_counter()
        try:
            row = generate_case(
                case=case,
                system=system,
                generator=active_generator,
                generator_name=generator_name,
                rag_engine=rag_engine,
                topk=topk,
            )
        except Exception as exc:  # pragma: no cover - surfaced in failure rows
            latency_ms = (time.perf_counter() - started) * 1000.0
            failed_cases += 1
            failure = _failure_row(
                case=case,
                dataset=dataset,
                system_name=system.name,
                generator_name=generator_name,
                runtime_meta=runtime_meta,
                latency_ms=latency_ms,
                exc=exc,
            )
            _append_jsonl_row(out_path, failure)
            latencies_ms.append(latency_ms)
            _sleep_between_calls(sleep_between_calls)
            continue
        latency_ms = (time.perf_counter() - started) * 1000.0
        completed_cases += 1
        row = _complete_row(
            row,
            dataset=dataset,
            generator_name=generator_name,
            runtime_meta=runtime_meta,
            latency_ms=latency_ms,
        )
        row.setdefault("trace", {})
        if isinstance(row["trace"], dict):
            row["trace"]["latency_ms"] = round(latency_ms, 3)
        latencies_ms.append(latency_ms)
        _append_jsonl_row(out_path, row)
        _sleep_between_calls(sleep_between_calls)
    latency_summary = _latency_summary(latencies_ms)
    summary = {
        "data": str(data_path),
        "dataset": dataset,
        "system": system_name,
        "generator": generator_name,
        **runtime_meta,
        "rag_db": str(rag_db_path),
        "topk": topk,
        "max_cases": max_cases,
        "case_start": case_start,
        "case_end": case_end,
        "resume": resume,
        "skip_existing": skip_existing,
        "overwrite": overwrite,
        "num_cases": len(cases),
        "completed_cases": completed_cases,
        "failed_cases": failed_cases,
        "skipped_cases": skipped_cases,
        "num_outputs": completed_cases + failed_cases,
        "num_skipped_existing": skipped_cases,
        "num_generated": completed_cases - skipped_cases,
        "num_failures": failed_cases,
        "avg_latency_ms": latency_summary.get("avg_ms"),
        "p95_latency_ms": latency_summary.get("p95_ms"),
        "latency_summary": latency_summary,
        "output": str(out_path),
    }
    write_json(summary_path, summary)
    return summary


def generate_case(
    *,
    case: DownstreamCase,
    system: DownstreamSystem,
    generator: BaseGenerator,
    generator_name: str,
    rag_engine: RagEngine,
    topk: int,
) -> dict[str, Any]:
    evidence = system.retrieve(case=case, rag_engine=rag_engine, topk=topk)
    trace = dict(system.last_trace)
    risk_context = _dict_value(trace.get("risk_context"))
    prompt = build_generation_prompt(
        case=case, system_name=system.name, risk_context=risk_context, evidence=evidence
    )
    raw_output = generator.generate(prompt)
    parsed_output = parse_generation_output(raw_output)
    return {
        "id": case.id,
        "system": system.name,
        "generator": generator_name,
        "raw_input": case.raw_input,
        "case": case.to_dict(),
        "prompt_hash": prompt_hash(prompt),
        "prompt": prompt,
        "raw_output": raw_output,
        "parsed_output": parsed_output,
        "risk_context": risk_context,
        "retrieved_evidence": [item.to_dict() for item in evidence],
        "predicted_protocol_id": parsed_output.get("protocol_id"),
        "trace": {
            **trace,
            "prompt_builder": system.name,
            "topk": topk,
            "parse_ok": bool(parsed_output.get("_parse_ok")),
        },
    }


def build_generation_prompt(
    *,
    case: DownstreamCase,
    system_name: str,
    risk_context: dict[str, Any],
    evidence: list[RetrievedEvidence],
) -> str:
    if system_name == "vanilla-rag":
        return build_vanilla_generation_prompt(case, evidence)
    if system_name == "rair-rag":
        return build_rair_generation_prompt(case, risk_context, evidence)
    msg = f"unsupported generation system: {system_name}"
    raise ValueError(msg)


def build_generator(
    generator_name: str,
    *,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> BaseGenerator:
    if generator_name == "local-llm":
        return LocalLlamaCppGenerator()
    if generator_name == "reference-llm":
        return ReferenceApiGenerator(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    msg = f"unsupported generator: {generator_name}"
    raise ValueError(msg)


def parse_generation_output(raw_output: str) -> dict[str, Any]:
    text = str(raw_output or "").strip()
    if not text:
        return {
            "protocol_id": None,
            "reply": "",
            "safety_notes": [],
            "used_evidence": [],
            "_parse_ok": False,
            "_parse_error": "empty output",
        }
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fallback_parsed_output(text, f"invalid JSON: {exc}")
    if not isinstance(payload, dict):
        return _fallback_parsed_output(text, "JSON output is not an object")
    return {
        "protocol_id": payload.get("protocol_id"),
        "reply": str(payload.get("reply") or ""),
        "safety_notes": _list_value(payload.get("safety_notes")),
        "used_evidence": _list_value(payload.get("used_evidence")),
        "_parse_ok": True,
    }


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _fallback_parsed_output(raw_text: str, error: str) -> dict[str, Any]:
    return {
        "protocol_id": None,
        "reply": raw_text,
        "safety_notes": [],
        "used_evidence": [],
        "_parse_ok": False,
        "_parse_error": error,
    }


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _default_rag_db_path() -> Path:
    return Path(os.getenv("RAG_DB_PATH") or settings.rag_db_path)


def _default_out_path(data_path: Path, system_name: str, generator_name: str) -> Path:
    out_dir = DEFAULT_GENERATION_DIR / generator_name.replace("-llm", "")
    return out_dir / f"{data_path.stem}_{system_name}_{generator_name}_outputs.jsonl"


def _default_summary_path(
    data_path: Path, system_name: str, generator_name: str
) -> Path:
    out_dir = DEFAULT_GENERATION_DIR / generator_name.replace("-llm", "")
    return out_dir / f"{data_path.stem}_{system_name}_{generator_name}_summary.json"


def _generator_runtime_metadata(
    generator: BaseGenerator, generator_name: str
) -> dict[str, Any]:
    if generator_name == "reference-llm":
        model = str(getattr(generator, "model", "") or DEFAULT_REFERENCE_MODEL)
        return {
            "model": model,
            "setting": "strong_hosted_reference",
            "generator_model": model,
            "generator_provider": DEFAULT_REFERENCE_PROVIDER,
            "generator_base_url": str(
                getattr(generator, "base_url", "")
                or DEFAULT_REFERENCE_BASE_URL
            ),
        }
    model_path = getattr(generator, "model_path", None)
    label = _local_model_label(model_path)
    return {
        "model": label,
        "setting": "edge_local",
        "generator_model": label,
        "generator_provider": "local-llm",
        "generator_base_url": None,
    }


def _default_runtime_metadata(generator_name: str) -> dict[str, Any]:
    if generator_name == "reference-llm":
        return {
            "model": DEFAULT_REFERENCE_MODEL,
            "setting": "strong_hosted_reference",
            "generator_model": DEFAULT_REFERENCE_MODEL,
            "generator_provider": DEFAULT_REFERENCE_PROVIDER,
            "generator_base_url": DEFAULT_REFERENCE_BASE_URL,
        }
    return {
        "model": "Qwen1.5-0.5B-Chat-Q4_K_M",
        "setting": "edge_local",
        "generator_model": "Qwen1.5-0.5B-Chat-Q4_K_M",
        "generator_provider": "local-llm",
        "generator_base_url": None,
    }


def _local_model_label(model_path: Any) -> str:
    if model_path is None:
        return "Qwen1.5-0.5B-Chat-Q4_K_M"
    path = Path(str(model_path))
    if path.name == DEFAULT_LOCAL_MODEL_PATH.rsplit("/", 1)[-1]:
        return "Qwen1.5-0.5B-Chat-Q4_K_M"
    return path.name or path.stem or "Qwen1.5-0.5B-Chat-Q4_K_M"


def _load_completed_rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and _is_completed_existing_row(payload):
            completed[str(payload.get("id"))] = payload
    return completed


def _is_completed_existing_row(row: dict[str, Any]) -> bool:
    if row.get("status") == "ok":
        return True
    if row.get("status") == "failed" or row.get("error"):
        return False
    return row.get("raw_output") is not None


def _append_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
        handle.flush()


def _prepare_output_path(path: Path, *, overwrite: bool, resumable: bool) -> None:
    if not path.exists():
        return
    if overwrite:
        path.write_text("", encoding="utf-8")
        return
    if resumable:
        return
    msg = (
        f"Output already exists: {path}. Use --resume/--skip-existing to continue "
        "without repeating completed samples, or pass --overwrite to replace this "
        "specific output file."
    )
    raise FileExistsError(msg)


def _complete_row(
    row: dict[str, Any],
    *,
    dataset: str,
    generator_name: str,
    runtime_meta: dict[str, Any],
    latency_ms: float,
) -> dict[str, Any]:
    completed = _with_runtime_metadata(row, runtime_meta)
    completed.update(
        {
            "dataset": dataset,
            "generator": generator_name,
            "status": "ok",
            "error": None,
            "latency_ms": round(latency_ms, 3),
        }
    )
    return completed


def _failure_row(
    *,
    case: DownstreamCase,
    dataset: str,
    system_name: str,
    generator_name: str,
    runtime_meta: dict[str, Any],
    latency_ms: float,
    exc: Exception,
) -> dict[str, Any]:
    error = f"{type(exc).__name__}: {exc}"
    return {
        "id": case.id,
        "dataset": dataset,
        "system": system_name,
        "generator": generator_name,
        **runtime_meta,
        "setting": runtime_meta.get("setting"),
        "status": "failed",
        "error": error,
        "raw_input": case.raw_input,
        "case": case.to_dict(),
        "latency_ms": round(latency_ms, 3),
        "trace": {
            "failed": True,
            "error": error,
            "latency_ms": round(latency_ms, 3),
        },
    }


def _with_runtime_metadata(
    row: dict[str, Any], runtime_meta: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(row)
    for key, value in runtime_meta.items():
        if merged.get(key) in (None, ""):
            merged[key] = value
    return merged


def _coerce_latency_ms(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sleep_between_calls(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _latency_summary(values_ms: list[float]) -> dict[str, float | int]:
    if not values_ms:
        return {"count": 0}
    values = sorted(values_ms)
    count = len(values)
    avg = sum(values) / count
    p50 = values[int((count - 1) * 0.5)]
    p95 = values[int((count - 1) * 0.95)]
    return {
        "count": count,
        "avg_ms": round(avg, 3),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(values[-1], 3),
    }


if __name__ == "__main__":
    main()
