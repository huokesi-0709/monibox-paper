from __future__ import annotations

import csv

import pytest

from benchmarks.annotation_agreement import cohen_kappa, compute_agreement


def _write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_cohen_kappa_returns_one_for_perfect_agreement():
    assert cohen_kappa(["high", "low"], ["high", "low"]) == pytest.approx(1.0)


def test_compute_agreement_reports_categorical_and_multilabel_metrics(tmp_path):
    base = {
        "expected_protocol_id": "prot_bleeding_control",
        "gold_chunk_ids": "chunk_a",
        "unsafe_actions": "止血带;注射",
    }
    rows_a = [
        {
            "case_id": "c1",
            "risk_level": "high",
            "expected_route": "severe_bleeding",
            "expected_primary_intent": "severe_bleeding",
            "expected_tags": "出血;腿",
            **base,
        },
        {
            "case_id": "c2",
            "risk_level": "low",
            "expected_route": "out_of_scope",
            "expected_protocol_id": "",
            "expected_primary_intent": "out_of_scope",
            "expected_tags": "",
            "gold_chunk_ids": "",
            "unsafe_actions": "保证获救",
        },
    ]
    rows_b = [
        {
            "case_id": "c1",
            "risk_level": "high",
            "expected_route": "severe_bleeding",
            "expected_primary_intent": "severe_bleeding",
            "expected_tags": "出血",
            **base,
        },
        {
            "case_id": "c2",
            "risk_level": "medium",
            "expected_route": "out_of_scope",
            "expected_protocol_id": "",
            "expected_primary_intent": "out_of_scope",
            "expected_tags": "",
            "gold_chunk_ids": "",
            "unsafe_actions": "保证获救",
        },
    ]
    path_a = tmp_path / "a.csv"
    path_b = tmp_path / "b.csv"
    _write_rows(path_a, rows_a)
    _write_rows(path_b, rows_b)

    report = compute_agreement(path_a, path_b)

    assert report["num_common_cases"] == 2
    assert report["categorical_fields"]["expected_route"]["cohen_kappa"] == pytest.approx(1.0)
    assert report["categorical_fields"]["risk_level"]["raw_agreement"] == pytest.approx(0.5)
    assert report["multilabel_fields"]["expected_tags"]["mean_jaccard"] == pytest.approx(0.75)


def test_compute_agreement_requires_overlapping_case_ids(tmp_path):
    path_a = tmp_path / "a.csv"
    path_b = tmp_path / "b.csv"
    rows = [
        {
            "case_id": "c1",
            "risk_level": "high",
            "expected_route": "severe_bleeding",
            "expected_protocol_id": "",
            "expected_primary_intent": "severe_bleeding",
            "expected_tags": "",
            "gold_chunk_ids": "",
            "unsafe_actions": "",
        }
    ]
    _write_rows(path_a, rows)
    rows[0]["case_id"] = "c2"
    _write_rows(path_b, rows)

    with pytest.raises(ValueError, match="no overlapping"):
        compute_agreement(path_a, path_b)
