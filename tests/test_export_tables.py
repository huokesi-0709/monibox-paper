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

    result = export_tables(eval_dir, out_dir)

    assert result["counts"]["main_results"] == 1
    assert result["counts"]["robustness_results"] == 1
    assert result["counts"]["ablation_results"] == 1
    assert result["counts"]["de_effect_results"] == 1

    main_rows = _read_csv(eval_dir / "main_results.csv")
    robust_rows = _read_csv(eval_dir / "robustness_results.csv")
    de_rows = _read_csv(eval_dir / "de_effect_results.csv")

    assert main_rows[0]["method"] == "hsc-rag-de"
    assert main_rows[0]["evidence_hit_at_5"] == "0.5"
    assert robust_rows[0]["robust_route_accuracy"] == "0.8"
    assert de_rows[0]["policy"] == "scoring/policy_de.json"
    assert (out_dir / "main_results.md").exists()
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
    assert _read_csv(eval_dir / "main_results.csv") == []
