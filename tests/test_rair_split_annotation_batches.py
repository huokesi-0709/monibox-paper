from __future__ import annotations

import csv
from pathlib import Path

import pytest

from benchmarks.rair_rag.scripts.split_annotation_batches import (
    split_annotation_batches,
)


def test_split_annotation_batches_samples_same_rows_for_a_and_b(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.csv"
    out_a = tmp_path / "a.csv"
    out_b = tmp_path / "b.csv"
    fieldnames = [
        "id",
        "raw_input",
        "human_accept",
        "annotator_primary_intent",
    ]
    write_rows(
        input_path,
        fieldnames,
        [{"id": f"case_{index}", "raw_input": str(index)} for index in range(10)],
    )

    result = split_annotation_batches(
        input_path=input_path,
        out_a=out_a,
        out_b=out_b,
        sample_size=5,
        seed=7,
        overwrite=False,
    )

    rows_a = read_rows(out_a)
    rows_b = read_rows(out_b)
    assert result["rows_out_A"] == 5
    assert [row["id"] for row in rows_a] == [row["id"] for row in rows_b]
    assert {row["annotator_id"] for row in rows_a} == {"A"}
    assert {row["annotator_id"] for row in rows_b} == {"B"}
    assert all(row["human_accept"] == "" for row in rows_a)
    assert all(row["annotator_primary_intent"] == "" for row in rows_a)
    assert "annotator_operational_constraints" in rows_a[0]
    assert "annotator_should_not_trigger" in rows_a[0]
    assert "annotator_notes" in rows_a[0]

    with pytest.raises(FileExistsError):
        split_annotation_batches(
            input_path=input_path,
            out_a=out_a,
            out_b=out_b,
            sample_size=5,
            seed=7,
            overwrite=False,
        )


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

