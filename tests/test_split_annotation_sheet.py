from __future__ import annotations

import csv

import pytest

from benchmarks.split_annotation_sheet import split_sheet


def test_split_sheet_writes_expected_batches(tmp_path):
    source = tmp_path / "annotator_a.csv"
    with source.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "query"])
        writer.writeheader()
        for index in range(5):
            writer.writerow({"case_id": f"clean_{index:04d}", "query": "q"})

    count = split_sheet(source, tmp_path / "batches", batch_size=2)

    assert count == 3
    assert (tmp_path / "batches" / "annotator_a_batch_01.csv").exists()
    rows = list(
        csv.DictReader(
            (tmp_path / "batches" / "annotator_a_batch_03.csv").open(
                encoding="utf-8", newline=""
            )
        )
    )
    assert len(rows) == 1


def test_split_sheet_rejects_non_positive_batch_size(tmp_path):
    source = tmp_path / "annotator_a.csv"
    source.write_text("case_id,query\nclean_0001,q\n", encoding="utf-8")

    with pytest.raises(ValueError, match="positive"):
        split_sheet(source, tmp_path / "batches", batch_size=0)
