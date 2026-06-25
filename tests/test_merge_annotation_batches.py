from __future__ import annotations

import csv

import pytest

from benchmarks.merge_annotation_batches import merge_batches


def _write_batch(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "query"])
        writer.writeheader()
        writer.writerows(rows)


def test_merge_batches_preserves_order_and_rows(tmp_path):
    source = tmp_path / "batches"
    source.mkdir()
    _write_batch(source / "batch_01.csv", [{"case_id": "c1", "query": "q1"}])
    _write_batch(source / "batch_02.csv", [{"case_id": "c2", "query": "q2"}])

    count = merge_batches(source, tmp_path / "merged.csv")

    rows = list(csv.DictReader((tmp_path / "merged.csv").open(encoding="utf-8")))
    assert count == 2
    assert [row["case_id"] for row in rows] == ["c1", "c2"]


def test_merge_batches_rejects_duplicate_case_ids(tmp_path):
    source = tmp_path / "batches"
    source.mkdir()
    _write_batch(source / "batch_01.csv", [{"case_id": "c1", "query": "q1"}])
    _write_batch(source / "batch_02.csv", [{"case_id": "c1", "query": "q2"}])

    with pytest.raises(ValueError, match="duplicate case_id"):
        merge_batches(source, tmp_path / "merged.csv")
