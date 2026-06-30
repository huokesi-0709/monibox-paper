from __future__ import annotations

import argparse
import json
import os
import platform
from time import perf_counter_ns
from pathlib import Path
from statistics import mean
from typing import Any

from benchmarks.rair_rag.routing_schema import load_routing_cases
from runtime.risk_router import RiskAwareInputRouter

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "build" / "rair_eval" / "runtime_latency_summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure RAIR runtime latency.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    summary = build_runtime_latency_summary(
        data_path=args.data,
        out_path=args.out,
        warmup=args.warmup,
        repeat=args.repeat,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def build_runtime_latency_summary(
    *,
    data_path: Path,
    out_path: Path,
    warmup: int,
    repeat: int,
) -> dict[str, Any]:
    cases = load_routing_cases(data_path)
    router = RiskAwareInputRouter()
    for case in cases[: max(0, warmup)]:
        router.route(case.raw_input, case.canonical_input)

    latencies: list[float] = []
    for _ in range(max(1, repeat)):
        for case in cases:
            start_ns = perf_counter_ns()
            router.route(case.raw_input, case.canonical_input)
            elapsed_ns = perf_counter_ns() - start_ns
            latencies.append(elapsed_ns / 1_000_000.0)

    summary = {
        "data_path": str(data_path),
        "num_cases": len(cases),
        "num_measurements": len(latencies),
        "warmup_cases": min(max(0, warmup), len(cases)),
        "repeat": max(1, repeat),
        "avg_latency_ms": float(mean(latencies)) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 95),
        "max_latency_ms": max(latencies) if latencies else 0.0,
        "min_latency_ms": min(latencies) if latencies else 0.0,
        "measurement_status": "measured" if latencies else "empty",
        "timer": "time.perf_counter_ns",
        "test_device": f"{platform.system()} {platform.release()} / CPU cores={os.cpu_count()}",
        "gpu_used": False,
        "embedding_precomputed": True,
        "online_llm_used": False,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


if __name__ == "__main__":
    main()
