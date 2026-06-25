from __future__ import annotations

import csv
import json

from benchmarks.final_labels_to_benchmark import convert_final_labels


def test_convert_final_labels_writes_clean_splits(tmp_path):
    final_labels = tmp_path / "final_labels.csv"
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
        "adjudication_note",
    ]
    rows = [
        {
            "case_id": f"clean_{index:04d}",
            "query": f"query {index}",
            "scenario": "severe_bleeding" if index <= 2 else "out_of_scope",
            "risk_level": "high" if index <= 2 else "low",
            "expected_route": "severe_bleeding" if index <= 2 else "out_of_scope",
            "expected_protocol_id": "prot_bleeding_control" if index <= 2 else "",
            "expected_primary_intent": "severe_bleeding" if index <= 2 else "out_of_scope",
            "expected_tags": "出血;腿" if index <= 2 else "",
            "gold_chunk_ids": "",
            "unsafe_actions": "止血带" if index <= 2 else "保证获救",
            "reference_reply": "安全回复。",
            "adjudication_note": "test",
        }
        for index in range(1, 5)
    ]
    with final_labels.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    stats = convert_final_labels(
        final_labels, tmp_path / "clean_dev.jsonl", tmp_path / "clean_test.jsonl", dev_size=2
    )

    assert stats["clean_dev"] == 2
    assert stats["clean_test"] == 2
    first = json.loads((tmp_path / "clean_dev.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first["perturbation_type"] == "clean"
    assert isinstance(first["expected_tags"], list)
