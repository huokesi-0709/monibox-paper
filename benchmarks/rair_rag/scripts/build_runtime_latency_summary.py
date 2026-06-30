from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PREDICTIONS = PROJECT_ROOT / "build" / "rair_eval" / "rair_test_risk-router_predictions.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "build" / "rair_eval" / "runtime_latency_summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAIR runtime latency summary.")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    summary = build_runtime_latency_summary(args.predictions, args.out)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def build_runtime_latency_summary(predictions_path: Path, out_path: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in predictions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latencies = [float(row.get("latency_ms") or row.get("trace", {}).get("latency_ms") or 0.0) for row in rows]
    latencies = [value for value in latencies if value > 0]
    summary = {
        "predictions_path": str(predictions_path),
        "num_cases": len(rows),
        "avg_latency_ms": float(mean(latencies)) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 95),
        "max_latency_ms": max(latencies) if latencies else 0.0,
        "test_device": "CPU / RAM / Windows",
        "gpu_used": False,
        "embedding_precomputed": True,
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
