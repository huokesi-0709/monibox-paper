from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from app.config import settings
from benchmarks.rair_rag.downstream.generation_eval import (
    DEFAULT_DATA,
    SUPPORTED_SYSTEMS,
    generate_case,
    write_json,
)
from benchmarks.rair_rag.downstream.llm_clients import (
    DEFAULT_REFERENCE_BASE_URL,
    DEFAULT_REFERENCE_MODEL,
    DEFAULT_REFERENCE_PROVIDER,
    ReferenceApiGenerator,
)
from benchmarks.rair_rag.downstream.retrieval_eval import load_downstream_cases
from benchmarks.rair_rag.downstream.schema import DownstreamCase
from runtime.rag_engine import RagEngine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = (
    PROJECT_ROOT
    / "build"
    / "downstream_eval"
    / "generation"
    / "reference_latency_subset"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure reference-llm generation latency on a stratified subset."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--systems",
        nargs="+",
        choices=sorted(SUPPORTED_SYSTEMS),
        default=["vanilla-rag", "rair-rag"],
    )
    parser.add_argument("--generator", choices=["reference-llm"], default="reference-llm")
    parser.add_argument("--sample-per-perturbation", type=int, default=20)
    parser.add_argument("--rag-db", type=Path, default=_default_rag_db_path())
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sleep-between-calls", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--max-retries", type=int)
    args = parser.parse_args()

    summary_path = args.summary or (args.out / "reference_latency_subset_summary.json")
    try:
        summary = run_latency_subset(
            data_path=args.data,
            systems=args.systems,
            generator_name=args.generator,
            sample_per_perturbation=args.sample_per_perturbation,
            rag_db_path=args.rag_db,
            out_dir=args.out,
            summary_path=summary_path,
            topk=args.topk,
            seed=args.seed,
            sleep_between_calls=args.sleep_between_calls,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_latency_subset(
    *,
    data_path: Path,
    systems: list[str],
    generator_name: str,
    sample_per_perturbation: int,
    rag_db_path: Path,
    out_dir: Path,
    summary_path: Path,
    topk: int = 3,
    seed: int = 42,
    sleep_between_calls: float = 0.0,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> dict[str, Any]:
    if generator_name != "reference-llm":
        raise ValueError("latency subset benchmark currently supports reference-llm only")
    if sample_per_perturbation <= 0:
        raise ValueError("--sample-per-perturbation must be positive")
    if topk <= 0:
        raise ValueError("--topk must be positive")
    if sleep_between_calls < 0:
        raise ValueError("--sleep-between-calls must be non-negative")
    unsupported = [system for system in systems if system not in SUPPORTED_SYSTEMS]
    if unsupported:
        raise ValueError(f"unsupported system(s): {', '.join(unsupported)}")
    if not rag_db_path.exists():
        raise FileNotFoundError(f"RAG database not found: {rag_db_path}")

    cases = load_downstream_cases(data_path)
    sampled_cases, strata = stratified_sample_by_perturbation(
        cases,
        sample_per_perturbation=sample_per_perturbation,
        seed=seed,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    rag_engine = RagEngine(str(rag_db_path))
    generator = ReferenceApiGenerator(
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )

    run_summaries = []
    for system_name in systems:
        output_path = (
            out_dir
            / f"{data_path.stem}_{system_name}_{generator_name}_latency_subset.jsonl"
        )
        run_summary = _run_system_latency_subset(
            cases=sampled_cases,
            system_name=system_name,
            generator_name=generator_name,
            generator=generator,
            rag_engine=rag_engine,
            data_path=data_path,
            out_path=output_path,
            topk=topk,
            sleep_between_calls=sleep_between_calls,
        )
        run_summaries.append(run_summary)

    all_latencies = [
        value
        for run in run_summaries
        for value in run.get("_latencies_ms", [])
        if isinstance(value, (int, float))
    ]
    failed_cases = sum(int(run["FailedCases"]) for run in run_summaries)
    summary = {
        "data": str(data_path),
        "generator": generator_name,
        "model": str(generator.model or DEFAULT_REFERENCE_MODEL),
        "provider": DEFAULT_REFERENCE_PROVIDER,
        "base_url": str(generator.base_url or DEFAULT_REFERENCE_BASE_URL),
        "setting": "strong_hosted_reference",
        "latency_measurement": "stratified_subset",
        "systems": systems,
        "sample_per_perturbation": sample_per_perturbation,
        "seed": seed,
        "topk": topk,
        "strata": strata,
        "outputs": [run["output"] for run in run_summaries],
        "runs": [_public_run_summary(run) for run in run_summaries],
        "NumCases": sum(int(run["NumCases"]) for run in run_summaries),
        "FailedCases": failed_cases,
        **_latency_fields(all_latencies),
        "note": (
            "qwen-plus generation latency is measured on a stratified subset; "
            "it is not the full 480-case content-generation latency."
        ),
    }
    write_json(summary_path, summary)
    return summary


def stratified_sample_by_perturbation(
    cases: list[DownstreamCase], *, sample_per_perturbation: int, seed: int
) -> tuple[list[DownstreamCase], dict[str, Any]]:
    groups: dict[str, list[DownstreamCase]] = {}
    for case in cases:
        perturbations = case.perturbation_types or ["unknown"]
        for perturbation in perturbations:
            groups.setdefault(perturbation, []).append(case)

    rng = random.Random(seed)
    selected: dict[str, DownstreamCase] = {}
    strata: dict[str, Any] = {}
    for perturbation in sorted(groups):
        group = sorted(groups[perturbation], key=lambda item: item.id)
        sample_size = min(sample_per_perturbation, len(group))
        sample = rng.sample(group, sample_size)
        for case in sample:
            selected.setdefault(case.id, case)
        strata[perturbation] = {
            "available": len(group),
            "sampled": sample_size,
            "sampled_ids": sorted(case.id for case in sample),
        }

    sampled_cases = sorted(selected.values(), key=lambda item: item.id)
    return sampled_cases, strata


def _run_system_latency_subset(
    *,
    cases: list[DownstreamCase],
    system_name: str,
    generator_name: str,
    generator: ReferenceApiGenerator,
    rag_engine: RagEngine,
    data_path: Path,
    out_path: Path,
    topk: int,
    sleep_between_calls: float,
) -> dict[str, Any]:
    system = SUPPORTED_SYSTEMS[system_name]()
    latencies_ms: list[float] = []
    failed_cases = 0
    completed_cases = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            started = time.perf_counter()
            try:
                row = generate_case(
                    case=case,
                    system=system,
                    generator=generator,
                    generator_name=generator_name,
                    rag_engine=rag_engine,
                    topk=topk,
                )
            except Exception as exc:  # pragma: no cover - depends on remote API
                latency_ms = (time.perf_counter() - started) * 1000.0
                failed_cases += 1
                row = _failed_row(
                    case=case,
                    data_path=data_path,
                    system_name=system_name,
                    generator=generator,
                    generator_name=generator_name,
                    latency_ms=latency_ms,
                    exc=exc,
                )
            else:
                latency_ms = (time.perf_counter() - started) * 1000.0
                completed_cases += 1
                latencies_ms.append(latency_ms)
                metadata = _common_metadata(
                    case=case,
                    data_path=data_path,
                    system_name=system_name,
                    generator=generator,
                    generator_name=generator_name,
                    latency_ms=latency_ms,
                    status="ok",
                )
                row_trace = row.get("trace") if isinstance(row.get("trace"), dict) else {}
                row.update(metadata)
                row["trace"] = {**row_trace, "latency_ms": round(latency_ms, 3)}
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            handle.flush()
            if sleep_between_calls > 0:
                time.sleep(sleep_between_calls)

    summary = {
        "system": system_name,
        "output": str(out_path),
        "NumCases": len(cases),
        "CompletedCases": completed_cases,
        "FailedCases": failed_cases,
        **_latency_fields(latencies_ms),
        "_latencies_ms": latencies_ms,
    }
    return summary


def _common_metadata(
    *,
    case: DownstreamCase,
    data_path: Path,
    system_name: str,
    generator: ReferenceApiGenerator,
    generator_name: str,
    latency_ms: float,
    status: str,
) -> dict[str, Any]:
    return {
        "dataset": data_path.stem,
        "system": system_name,
        "generator": generator_name,
        "model": str(generator.model or DEFAULT_REFERENCE_MODEL),
        "setting": "strong_hosted_reference",
        "latency_measurement": "stratified_subset",
        "status": status,
        "latency_ms": round(latency_ms, 3),
        "perturbation_types": list(case.perturbation_types),
    }


def _failed_row(
    *,
    case: DownstreamCase,
    data_path: Path,
    system_name: str,
    generator: ReferenceApiGenerator,
    generator_name: str,
    latency_ms: float,
    exc: Exception,
) -> dict[str, Any]:
    error = f"{type(exc).__name__}: {exc}"
    return {
        "id": case.id,
        "raw_input": case.raw_input,
        "case": case.to_dict(),
        "error": error,
        **_common_metadata(
            case=case,
            data_path=data_path,
            system_name=system_name,
            generator=generator,
            generator_name=generator_name,
            latency_ms=latency_ms,
            status="failed",
        ),
        "trace": {"failed": True, "error": error, "latency_ms": round(latency_ms, 3)},
    }


def _latency_fields(values_ms: list[float]) -> dict[str, float | None]:
    if not values_ms:
        return {
            "AvgLatencyMs": None,
            "P50LatencyMs": None,
            "P95LatencyMs": None,
            "MaxLatencyMs": None,
        }
    values = sorted(values_ms)
    count = len(values)
    return {
        "AvgLatencyMs": round(sum(values) / count, 3),
        "P50LatencyMs": round(values[int((count - 1) * 0.5)], 3),
        "P95LatencyMs": round(values[int((count - 1) * 0.95)], 3),
        "MaxLatencyMs": round(values[-1], 3),
    }


def _public_run_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in run.items() if key != "_latencies_ms"}


def _default_rag_db_path() -> Path:
    return Path(settings.rag_db_path)


if __name__ == "__main__":
    main()
