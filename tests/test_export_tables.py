from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.export_tables import export_tables


def _write_json(path: Path, obj: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _csv_fields(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f).fieldnames or [])


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_export_tables_generates_csv_and_markdown(tmp_path):
    eval_dir = tmp_path / "eval"
    out_dir = eval_dir / "tables"
    _write_json(
        eval_dir / "clean" / "clean_hsc-rag-de_summary.json",
        {
            "data": "benchmarks/data/clean_dev.jsonl",
            "method": "hsc-rag-de",
            "route_accuracy": 1.0,
            "evidence_hit_at_3": 0.5,
            "high_risk_recall": 1.0,
            "unsafe_response_rate": 0.0,
            "unsupported_claim_rate": 0.0,
            "avg_latency_ms": 3.0,
            "p95_latency_ms": 8.0,
            "num_cases": 10,
            "num_predictions": 10,
            "num_evidence_eval_cases": 4,
            "num_high_risk_cases": 7,
            "num_protocol_eval_cases": 6,
        },
    )
    _write_json(
        eval_dir / "robust" / "robust_hsc-rag-de_summary.json",
        {
            "data": "benchmarks/data/robustness_dev.jsonl",
            "method": "hsc-rag-de",
            "route_accuracy": 0.8,
            "primary_intent_accuracy": 0.9,
            "protocol_false_trigger_rate": 0.1,
            "robust_consistency": 0.7,
            "unsafe_response_rate": 0.0,
            "avg_latency_ms": 4.0,
            "p95_latency_ms": 9.0,
            "num_cases": 10,
            "num_predictions": 10,
            "num_evidence_eval_cases": 4,
            "num_high_risk_cases": 7,
            "num_protocol_eval_cases": 6,
        },
    )
    _write_json(
        eval_dir / "ablation" / "clean_without_guard_summary.json",
        {
            "data": "benchmarks/data/clean_dev.jsonl",
            "method": "without_guard",
            "ablation": "without_guard",
            "disabled_modules": "safety_guard",
            "route_accuracy": 0.7,
            "high_risk_recall": 0.95,
            "unsafe_response_rate": 0.2,
            "num_cases": 10,
            "num_predictions": 10,
            "num_high_risk_cases": 7,
        },
    )
    _write_json(
        eval_dir / "de_best_metrics.json",
        {
            "output_policy_path": "scoring/policy_de.json",
            "best_trial": {
                "fitness": 0.75,
                "route_accuracy_clean": 1.0,
                "route_accuracy_robust": 0.8,
                "high_risk_miss_rate": 0.02,
                "unsafe_response_rate": 0.0,
            },
        },
    )
    _write_jsonl(
        eval_dir / "clean" / "clean_hsc-rag-de_predictions.jsonl",
        [
            {
                "method": "hsc-rag-de",
                "protocol_id": "prot_bleeding_control",
                "trace": {
                    "metadata": {"method": "hsc-rag-de", "suite": "clean"},
                    "protocol_id": "prot_bleeding_control",
                    "protocol_confidence": 0.8,
                    "decision": "protocol_direct",
                    "guard_level": "allow",
                    "top_chunks": [
                        {
                            "chunk_id": "chunk_a",
                            "score_breakdown": {"final_score": 0.9},
                        }
                    ],
                },
            }
        ],
    )
    _write_jsonl(
        eval_dir / "robust" / "robust_hsc-rag-de_predictions.jsonl",
        [
            {
                "method": "hsc-rag-de",
                "trace": {
                    "metadata": {"method": "hsc-rag-de", "suite": "robust"},
                    "low_evidence": True,
                    "decision": "low_evidence_rag_fallback",
                    "protocol_confidence": 0.2,
                    "guard_level": "block",
                    "guard_reasons": ["unsafe"],
                    "top_chunks": [],
                },
            }
        ],
    )

    result = export_tables(eval_dir, out_dir)

    assert result["counts"]["main_results"] == 1
    assert result["counts"]["robustness_results"] == 1
    assert result["counts"]["ablation_results"] == 1
    assert result["counts"]["de_effect_results"] == 1
    assert result["counts"]["trace_audit_results"] == 2

    main_rows = _read_csv(eval_dir / "main_results.csv")
    robust_rows = _read_csv(eval_dir / "robustness_results.csv")
    ablation_rows = _read_csv(eval_dir / "ablation_results.csv")
    de_rows = _read_csv(eval_dir / "de_effect_results.csv")
    trace_rows = _read_csv(eval_dir / "trace_audit_results.csv")

    assert main_rows[0]["method"] == "hsc-rag-de"
    assert main_rows[0]["evidence_hit_at_5"] == "0.5"
    assert main_rows[0]["num_cases"] == "10"
    assert main_rows[0]["num_predictions"] == "10"
    assert main_rows[0]["num_evidence_eval_cases"] == "4"
    assert main_rows[0]["num_high_risk_cases"] == "7"
    assert main_rows[0]["num_protocol_eval_cases"] == "6"
    assert robust_rows[0]["robust_route_accuracy"] == "0.8"
    assert robust_rows[0]["num_cases"] == "10"
    assert robust_rows[0]["num_predictions"] == "10"
    assert robust_rows[0]["num_evidence_eval_cases"] == "4"
    assert robust_rows[0]["num_high_risk_cases"] == "7"
    assert robust_rows[0]["num_protocol_eval_cases"] == "6"
    assert ablation_rows[0]["num_cases"] == "10"
    assert ablation_rows[0]["num_predictions"] == "10"
    assert ablation_rows[0]["num_high_risk_cases"] == "7"
    assert de_rows[0]["policy"] == "scoring/policy_de.json"
    assert {row["suite"] for row in trace_rows} == {"clean", "robust"}
    clean_trace = next(row for row in trace_rows if row["suite"] == "clean")
    robust_trace = next(row for row in trace_rows if row["suite"] == "robust")
    assert clean_trace["num_predictions"] == "1"
    assert clean_trace["num_with_trace"] == "1"
    assert clean_trace["low_evidence_rate"] == "0"
    assert clean_trace["avg_protocol_confidence"] == "0.8"
    assert clean_trace["num_with_score_breakdown"] == "1"
    assert robust_trace["num_low_evidence"] == "1"
    assert robust_trace["low_evidence_rate"] == "1"
    assert robust_trace["num_guarded"] == "1"
    assert (out_dir / "main_results.md").exists()
    assert (out_dir / "trace_audit_results.md").exists()
    assert "| method | route_accuracy |" in (
        out_dir / "main_results.md"
    ).read_text(encoding="utf-8")


def test_export_tables_missing_inputs_does_not_crash(tmp_path):
    eval_dir = tmp_path / "empty_eval"
    out_dir = eval_dir / "tables"

    result = export_tables(eval_dir, out_dir)

    assert result["warnings"]
    assert (eval_dir / "main_results.csv").exists()
    assert (out_dir / "main_results.md").exists()
    assert (eval_dir / "trace_audit_results.csv").exists()
    assert (out_dir / "trace_audit_results.md").exists()
    assert _read_csv(eval_dir / "main_results.csv") == []
    assert _read_csv(eval_dir / "trace_audit_results.csv") == []
    assert "num_evidence_eval_cases" in _csv_fields(eval_dir / "main_results.csv")
    assert "num_with_trace" in _csv_fields(eval_dir / "trace_audit_results.csv")
