from __future__ import annotations

from benchmarks.schema import BenchmarkCase


def baseline_reply(case: BenchmarkCase) -> str:
    """Deterministic offline baseline used for smoke tests and comparisons."""

    query = case.query.strip()
    if not query:
        return ""
    return "请先保持冷静，减少活动，描述最严重的问题。"
