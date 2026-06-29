from __future__ import annotations

import csv
from pathlib import Path

from benchmarks.rair_rag.scripts.merge_screening_suggestions import (
    merge_screening_suggestions,
)


def test_merge_screening_suggestions_splits_round_outputs(tmp_path: Path) -> None:
    base = tmp_path / "base.csv"
    suggestions = tmp_path / "suggestions.csv"
    merged = tmp_path / "merged.csv"
    annotator_a = tmp_path / "a.csv"
    annotator_b = tmp_path / "b.csv"
    rewrite_queue = tmp_path / "rewrite.csv"
    adjudication_queue = tmp_path / "adjudication.csv"
    fieldnames = [
        "id",
        "raw_input",
        "human_accept",
        "human_notes",
        "annotator_primary_intent",
        "annotator_negated_risks",
        "annotator_secondary_intents",
    ]
    write_rows(
        base,
        fieldnames,
        [
            {"id": "a", "raw_input": "a"},
            {"id": "b", "raw_input": "b"},
            {"id": "c", "raw_input": "c"},
        ],
    )
    write_rows(
        suggestions,
        fieldnames,
        [
            {
                "id": "a",
                "human_accept": "yes",
                "human_notes": "ok",
                "annotator_primary_intent": "respiratory_distress",
            },
            {
                "id": "b",
                "human_accept": "rewrite",
                "human_notes": "rewrite_raw_input: x",
                "annotator_primary_intent": "trauma_or_fracture",
            },
            {
                "id": "c",
                "human_accept": "needs_adjudication",
                "human_notes": "boundary",
                "annotator_primary_intent": "needs_adjudication",
            },
        ],
    )

    result = merge_screening_suggestions(
        base_path=base,
        suggestions_path=suggestions,
        merged_path=merged,
        annotator_a_path=annotator_a,
        annotator_b_path=annotator_b,
        rewrite_queue_path=rewrite_queue,
        adjudication_queue_path=adjudication_queue,
        overwrite=False,
    )

    assert result["merged"] == 3
    assert result["annotator_A"] == 1
    assert result["rewrite_queue"] == 1
    assert result["adjudication_queue"] == 1
    annotator_rows = read_rows(annotator_a)
    assert annotator_rows[0]["id"] == "a"
    assert annotator_rows[0]["human_accept"] == ""
    assert read_rows(rewrite_queue)[0]["id"] == "b"
    assert read_rows(adjudication_queue)[0]["id"] == "c"


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

