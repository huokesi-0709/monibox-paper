from __future__ import annotations

from collections import Counter

from benchmarks.build_clean_candidates import build_rows


def test_build_rows_has_formal_scale_and_unique_ids_queries():
    rows = build_rows()

    assert len(rows) >= 350
    assert len({row["case_id"] for row in rows}) == len(rows)
    assert len({row["query"] for row in rows}) == len(rows)


def test_build_rows_covers_required_scenarios():
    rows = build_rows()
    counts = Counter(row["scenario"] for row in rows)

    assert counts["severe_bleeding"] >= 35
    assert counts["respiratory_distress"] >= 35
    assert counts["trapped_or_crush"] >= 35
    assert counts["multi_intent"] >= 40
    assert counts["out_of_scope"] >= 25
    assert counts["unsafe_induction"] >= 25
    assert counts["negation_conflict"] >= 25
