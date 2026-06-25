from __future__ import annotations

import csv

import pytest

from benchmarks.prepare_annotation_sheets import prepare_sheet


def test_prepare_sheet_creates_blank_labels_from_candidates(tmp_path):
    candidates = tmp_path / "candidates.csv"
    candidates.write_text(
        "case_id,query,scenario,source_type,source_note\n"
        "clean_001,我的腿在流血,severe_bleeding,scenario_written,\n",
        encoding="utf-8",
    )
    out = tmp_path / "annotator_a.csv"

    count = prepare_sheet(candidates, out, "A")

    rows = list(csv.DictReader(out.open("r", encoding="utf-8", newline="")))
    assert count == 1
    assert rows[0]["case_id"] == "clean_001"
    assert rows[0]["annotator_id"] == "A"
    assert rows[0]["scenario"] == "severe_bleeding"
    assert rows[0]["risk_level"] == ""


def test_prepare_sheet_requires_case_id_and_query(tmp_path):
    candidates = tmp_path / "candidates.csv"
    candidates.write_text(
        "case_id,query,scenario\n"
        "clean_001,,severe_bleeding\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="case_id and query"):
        prepare_sheet(candidates, tmp_path / "annotator_a.csv", "A")
