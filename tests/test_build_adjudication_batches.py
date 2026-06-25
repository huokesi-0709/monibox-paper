from __future__ import annotations

import csv

from benchmarks.build_adjudication_batches import build_adjudication_batches


def _write(path, rows):
    fields = [
        "case_id",
        "query",
        "scenario",
        "risk_level",
        "expected_route",
        "expected_protocol_id",
        "expected_primary_intent",
        "expected_tags",
        "gold_chunk_ids",
        "unsafe_actions",
        "reference_reply",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_build_adjudication_batches_combines_a_b_rows(tmp_path):
    row = {
        "case_id": "clean_0001",
        "query": "q",
        "scenario": "severe_bleeding",
        "risk_level": "high",
        "expected_route": "severe_bleeding",
        "expected_protocol_id": "prot_bleeding_control",
        "expected_primary_intent": "severe_bleeding",
        "expected_tags": "出血",
        "gold_chunk_ids": "",
        "unsafe_actions": "止血带",
        "reference_reply": "按压伤口。",
    }
    _write(tmp_path / "a.csv", [row])
    b = {**row, "risk_level": "critical"}
    _write(tmp_path / "b.csv", [b])

    count = build_adjudication_batches(
        tmp_path / "a.csv", tmp_path / "b.csv", tmp_path / "out", batch_size=1
    )

    rows = list(
        csv.DictReader(
            (tmp_path / "out" / "adjudication_batch_01.csv").open(
                encoding="utf-8", newline=""
            )
        )
    )
    assert count == 1
    assert rows[0]["a_risk_level"] == "high"
    assert rows[0]["b_risk_level"] == "critical"
