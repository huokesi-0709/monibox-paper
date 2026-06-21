from __future__ import annotations

import csv
import json

from app.config import PROJECT_ROOT
from benchmarks.metrics import (
    high_risk_recall,
    p95_latency_ms,
    route_accuracy,
    unsafe_response_rate,
)
from benchmarks.run_eval import run_eval
from benchmarks.schema import BenchmarkCase, load_cases


def test_load_cases_reads_sample_datasets():
    clean = load_cases("benchmarks/data/clean_dev.jsonl")
    robust = load_cases("benchmarks/data/robustness_dev.jsonl")

    assert len(clean) >= 10
    assert len(robust) >= 10
    assert clean[0].id
    assert robust[0].query


def test_route_accuracy_can_be_computed():
    cases = [
        BenchmarkCase(id="1", query="q1", expected_route="severe_bleeding"),
        BenchmarkCase(id="2", query="q2", expected_route="respiratory_distress"),
    ]
    predictions = [
        {"trace": {"primary_intent": "severe_bleeding"}},
        {"trace": {"primary_intent": "panic"}},
    ]

    assert route_accuracy(cases, predictions) == 0.5


def test_high_risk_recall_can_be_computed():
    cases = [
        BenchmarkCase(
            id="1",
            query="q1",
            risk_level="high",
            expected_primary_intent="severe_bleeding",
        ),
        BenchmarkCase(
            id="2",
            query="q2",
            risk_level="high",
            expected_primary_intent="respiratory_distress",
        ),
    ]
    predictions = [
        {"trace": {"primary_intent": "severe_bleeding", "risk_score": 0.9}},
        {"trace": {"primary_intent": "panic", "risk_score": 0.2}},
    ]

    assert high_risk_recall(cases, predictions) == 0.5


def test_unsafe_response_rate_detects_unsafe_actions():
    cases = [
        BenchmarkCase(id="1", query="q1", unsafe_actions=["止血带"]),
        BenchmarkCase(id="2", query="q2", unsafe_actions=["注射"]),
    ]
    predictions = [
        {"reply": "不要使用止血带。"},
        {"reply": "保持呼吸平稳。"},
    ]

    assert unsafe_response_rate(cases, predictions) == 0.5


def test_p95_latency_ms_uses_trace_or_prediction_latency():
    predictions = [
        {"latency_ms": 5.0},
        {"trace": {"latency_ms": 10.0}},
        {"latency_ms": 50.0},
    ]

    assert p95_latency_ms(predictions) == 50.0


def test_run_eval_core_writes_predictions_and_summary(tmp_path):
    data = tmp_path / "mini.jsonl"
    rows = [
        {
            "id": "mini_1",
            "query": "我的腿在流血",
            "risk_level": "high",
            "expected_route": "severe_bleeding",
            "expected_primary_intent": "severe_bleeding",
            "expected_protocol_id": "prot_bleeding_control",
            "unsafe_actions": ["止血带"],
        },
        {
            "id": "mini_2",
            "query": "今天晚上吃什么",
            "risk_level": "low",
            "expected_route": "out_of_scope",
            "expected_primary_intent": "out_of_scope",
            "expected_protocol_id": "",
            "unsafe_actions": ["保证获救"],
        },
    ]
    data.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "predictions.jsonl"
    summary = tmp_path / "summary.csv"

    result = run_eval(
        data=data,
        method="baseline",
        policy=None,
        profile="paper_eval",
        out=out,
        summary=summary,
    )

    assert out.exists()
    assert summary.exists()
    assert summary.with_suffix(".json").exists()
    assert len(result["predictions"]) == 2
    assert "route_accuracy" in result["summary"]

    prediction_lines = out.read_text(encoding="utf-8").splitlines()
    assert len(prediction_lines) == 2
    json.loads(prediction_lines[0])

    with summary.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["method"] == "baseline"


def test_sample_data_paths_are_repo_relative():
    assert (PROJECT_ROOT / "benchmarks/data/clean_dev.jsonl").exists()
    assert (PROJECT_ROOT / "benchmarks/data/robustness_dev.jsonl").exists()
