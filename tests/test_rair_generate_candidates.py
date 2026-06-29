from __future__ import annotations

from pathlib import Path

from benchmarks.rair_rag.scripts.generate_candidates import generate_candidates


def test_generate_candidates_from_templates() -> None:
    candidates = generate_candidates(Path("benchmarks/rair_rag/templates"))

    assert len(candidates) == 817
    assert {candidate["id"].split("_")[0] for candidate in candidates} == {
        "boundary",
        "clean",
        "multi",
        "neg",
    }
    assert all(candidate["needs_human_review"] is True for candidate in candidates)
    assert all(
        candidate["source_type"] == "template_generated" for candidate in candidates
    )

    operational_only = [
        candidate
        for candidate in candidates
        if candidate["template_id"] == "clean_low_battery_001"
    ]
    assert operational_only
    assert all(candidate["expected_route"] is None for candidate in operational_only)
    assert all(
        candidate["operational_constraints"] == ["low_battery"]
        for candidate in operational_only
    )

