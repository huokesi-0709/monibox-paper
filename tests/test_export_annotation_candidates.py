from __future__ import annotations

import csv
import json

from benchmarks.export_annotation_candidates import (
    export_blank_annotator_sheet,
    export_candidates,
)


def test_export_candidates_uses_clean_query_and_intent(tmp_path):
    source = tmp_path / "clean.jsonl"
    source.write_text(
        json.dumps(
            {
                "id": "clean_001",
                "query": "raw",
                "clean_query": "clean",
                "expected_primary_intent": "severe_bleeding",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "candidates.csv"

    count = export_candidates(source, out)

    rows = list(csv.DictReader(out.open("r", encoding="utf-8", newline="")))
    assert count == 1
    assert rows[0]["case_id"] == "clean_001"
    assert rows[0]["query"] == "clean"
    assert rows[0]["scenario"] == "severe_bleeding"


def test_export_blank_annotator_sheet_leaves_labels_empty(tmp_path):
    source = tmp_path / "clean.jsonl"
    source.write_text(
        json.dumps(
            {
                "id": "clean_001",
                "query": "我的腿在流血",
                "risk_level": "high",
                "expected_primary_intent": "severe_bleeding",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "annotator_a.csv"

    count = export_blank_annotator_sheet(source, out, "A")

    rows = list(csv.DictReader(out.open("r", encoding="utf-8", newline="")))
    assert count == 1
    assert rows[0]["annotator_id"] == "A"
    assert rows[0]["query"] == "我的腿在流血"
    assert rows[0]["risk_level"] == ""
    assert rows[0]["expected_primary_intent"] == ""
