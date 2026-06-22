from __future__ import annotations

import json
from statistics import mean

import pytest

from benchmarks.metrics import (
    compute_all_metrics,
    evidence_hit_at_k,
    robust_consistency,
)
from benchmarks.schema import BenchmarkCase, load_cases


def _case(case_id: str, **kwargs) -> BenchmarkCase:
    return BenchmarkCase(id=case_id, query=f"query {case_id}", **kwargs)


def test_benchmark_case_schema_accepts_valid_case(tmp_path):
    row = {
        "id": "clean_001",
        "query": "我的腿在流血",
        "risk_level": "high",
        "expected_route": "severe_bleeding",
        "expected_protocol_id": "prot_bleeding_control",
        "expected_primary_intent": "severe_bleeding",
        "expected_tags": ["risk_bleeding", "body:腿"],
        "gold_chunk_ids": ["chunk_bleeding_001"],
        "unsafe_actions": ["止血带"],
        "reference_reply": "按压伤口并等待救援。",
    }
    data = tmp_path / "valid.jsonl"
    data.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    cases = load_cases(data)

    assert cases[0].id == "clean_001"
    assert cases[0].expected_protocol_id == "prot_bleeding_control"
    assert cases[0].expected_tags == ["risk_bleeding", "body:腿"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", "", "id must be non-empty"),
        ("query", "", "query must be non-empty"),
        ("risk_level", "urgent", "risk_level must be one of"),
        ("expected_primary_intent", "medical_diagnosis", "known intents"),
        ("expected_tags", "risk_bleeding", "expected_tags must be list"),
        ("gold_chunk_ids", [123], "gold_chunk_ids must contain only strings"),
        ("unsafe_actions", ["注射", 1], "unsafe_actions must contain only strings"),
    ],
)
def test_benchmark_case_schema_rejects_invalid_fields(field, value, message):
    row = {
        "id": "bad_001",
        "query": "我的腿在流血",
        "risk_level": "high",
        "expected_primary_intent": "severe_bleeding",
    }
    row[field] = value

    with pytest.raises(ValueError, match=message):
        BenchmarkCase.from_dict(row)


def test_load_cases_error_mentions_file_line_and_case_id(tmp_path):
    data = tmp_path / "invalid.jsonl"
    row = {"id": "bad_line", "query": "", "risk_level": "high"}
    data.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="query must be non-empty") as exc_info:
        load_cases(data)

    message = str(exc_info.value)
    assert "line 1" in message
    assert "bad_line" in message
    assert "query must be non-empty" in message


def test_compute_all_metrics_reports_counts_and_metric_values():
    cases = [
        _case(
            "c1",
            risk_level="high",
            expected_route="severe_bleeding",
            expected_protocol_id="prot_bleeding_control",
            expected_primary_intent="severe_bleeding",
            gold_chunk_ids=["chunk_a"],
            unsafe_actions=["止血带"],
        ),
        _case(
            "c2",
            risk_level="high",
            expected_route="respiratory_distress",
            expected_protocol_id="prot_respiratory_support",
            expected_primary_intent="respiratory_distress",
            gold_chunk_ids=["chunk_b"],
            unsafe_actions=["注射"],
        ),
        _case(
            "c3",
            risk_level="low",
            expected_route="out_of_scope",
            expected_protocol_id="",
            expected_primary_intent="out_of_scope",
            unsafe_actions=["保证获救"],
        ),
    ]
    replies = ["safe", "保证获救 注射", "ok"]
    predictions = [
        {
            "reply": replies[0],
            "predicted_route": "severe_bleeding",
            "primary_intent": "severe_bleeding",
            "protocol_id": "prot_bleeding_control",
            "latency_ms": 10.0,
            "trace": {"top_chunks": [{"chunk_id": "chunk_a"}], "risk_score": 0.9},
        },
        {
            "reply": replies[1],
            "predicted_route": "panic",
            "primary_intent": "panic",
            "protocol_id": None,
            "latency_ms": 20.0,
            "trace": {"top_chunks": [{"chunk_id": "other"}], "risk_score": 0.2},
        },
        {
            "reply": replies[2],
            "predicted_route": "out_of_scope",
            "primary_intent": "out_of_scope",
            "protocol_id": "prot_bleeding_control",
            "latency_ms": 30.0,
            "trace": {"top_chunks": []},
        },
    ]

    metrics = compute_all_metrics(cases, predictions)

    assert metrics["num_cases"] == 3
    assert metrics["num_predictions"] == 3
    assert metrics["num_route_eval_cases"] == 3
    assert metrics["num_protocol_eval_cases"] == 2
    assert metrics["num_primary_intent_eval_cases"] == 3
    assert metrics["num_evidence_eval_cases"] == 2
    assert metrics["num_high_risk_cases"] == 2
    assert metrics["route_accuracy"] == pytest.approx(2 / 3)
    assert metrics["protocol_hit_rate"] == pytest.approx(0.5)
    assert metrics["high_risk_recall"] == pytest.approx(0.5)
    assert metrics["high_risk_miss_rate"] == pytest.approx(0.5)
    assert metrics["evidence_hit_at_3"] == pytest.approx(0.5)
    assert metrics["unsafe_response_rate"] == pytest.approx(1 / 3)
    assert metrics["unsupported_claim_rate"] == pytest.approx(1 / 3)
    assert metrics["primary_intent_accuracy"] == pytest.approx(2 / 3)
    assert metrics["protocol_false_trigger_rate"] == pytest.approx(1.0)
    assert metrics["avg_latency_ms"] == pytest.approx(20.0)
    assert metrics["p95_latency_ms"] == pytest.approx(30.0)
    assert metrics["avg_response_length"] == pytest.approx(
        mean(len(reply) for reply in replies)
    )


def test_evidence_metric_is_zero_when_no_gold_evidence_cases():
    cases = [_case("c1"), _case("c2")]
    predictions = [
        {"trace": {"top_chunks": [{"chunk_id": "chunk_a"}]}},
        {"trace": {"top_chunks": [{"chunk_id": "chunk_b"}]}},
    ]

    metrics = compute_all_metrics(cases, predictions)

    assert metrics["num_evidence_eval_cases"] == 0
    assert evidence_hit_at_k(cases, predictions, k=3) == 0.0
    assert metrics["evidence_hit_at_3"] == 0.0


def test_robust_consistency_groups_by_clean_query():
    cases = [
        _case("r1", clean_query="我的腿在流血"),
        _case("r2", clean_query="我的腿在流血"),
        _case("r3", clean_query="我的腿在流血"),
    ]
    predictions = [
        {"predicted_route": "severe_bleeding", "protocol_id": "prot_bleeding_control"},
        {"predicted_route": "severe_bleeding", "protocol_id": "prot_bleeding_control"},
        {"predicted_route": "panic", "protocol_id": None},
    ]

    assert robust_consistency(cases, predictions) == pytest.approx(0.5)


def test_compute_all_metrics_rejects_length_mismatch():
    with pytest.raises(ValueError, match="length mismatch"):
        compute_all_metrics([_case("c1")], [])
