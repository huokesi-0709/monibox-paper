from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.export_rair_tables import export_rair_tables


def _write_json(path: Path, obj: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_export_rair_tables_generates_named_tables(tmp_path: Path) -> None:
    eval_dir = tmp_path / "rair_eval"
    out_dir = eval_dir / "tables"
    _write_json(
        eval_dir / "rair_test_risk-router_summary.json",
        {
            "data": "benchmarks/rair_rag/data/test/rair_test.jsonl",
            "method": "risk-router",
            "metrics": {
                "RouteAcc": 0.9,
                "HRR": 0.95,
                "PFTR": 0.02,
                "NegRiskF1": 0.7,
                "SecondaryIntentF1": 0.8,
                "ConstraintF1": 0.9,
                "SuppressedProtocolF1": 0.6,
                "RiskCandidateF1": 0.85,
                "by_perturbation_type": {
                    "clean_control": {
                        "RouteAcc": 1.0,
                        "HRR": 1.0,
                        "PFTR": 0.0,
                        "NegRiskF1": 0.0,
                        "SecondaryIntentF1": 0.9,
                        "ConstraintF1": 0.0,
                        "SuppressedProtocolF1": 0.0,
                        "RiskCandidateF1": 1.0,
                        "num_cases": 65,
                    },
                    "negation_conflict": {
                        "RouteAcc": 0.8,
                        "HRR": 0.9,
                        "PFTR": 0.03,
                        "NegRiskF1": 0.75,
                        "SecondaryIntentF1": 0.0,
                        "ConstraintF1": 1.0,
                        "SuppressedProtocolF1": 0.7,
                        "RiskCandidateF1": 0.8,
                        "num_cases": 152,
                    },
                },
                "num_cases": 217,
            },
            "num_cases": 217,
        },
    )
    _write_json(
        eval_dir / "rair_test_no-negation_summary.json",
        {
            "data": "benchmarks/rair_rag/data/test/rair_test.jsonl",
            "method": "no-negation",
            "metrics": {
                "RouteAcc": 0.8,
                "HRR": 0.9,
                "PFTR": 0.03,
                "NegRiskF1": 0.74,
                "SecondaryIntentF1": 0.0,
                "ConstraintF1": 1.0,
                "SuppressedProtocolF1": 0.5,
                "RiskCandidateF1": 0.8,
                "by_perturbation_type": {
                    "multi_intent": {
                        "RouteAcc": 0.8,
                        "HRR": 1.0,
                        "PFTR": 0.0,
                        "NegRiskF1": 0.0,
                        "SecondaryIntentF1": 0.85,
                        "ConstraintF1": 1.0,
                        "SuppressedProtocolF1": 0.5,
                        "RiskCandidateF1": 0.8,
                        "num_cases": 100,
                    }
                },
                "num_cases": 100,
            },
            "num_cases": 100,
        },
    )
    _write_json(
        eval_dir / "rair_test_single-intent_summary.json",
        {
            "data": "benchmarks/rair_rag/data/test/rair_test.jsonl",
            "method": "single-intent",
            "metrics": {
                "RouteAcc": 0.7,
                "HRR": 0.85,
                "PFTR": 0.05,
                "NegRiskF1": 0.6,
                "SecondaryIntentF1": 0.0,
                "ConstraintF1": 0.95,
                "SuppressedProtocolF1": 0.45,
                "RiskCandidateF1": 0.75,
                "by_perturbation_type": {
                    "multi_intent": {
                        "RouteAcc": 0.7,
                        "HRR": 0.8,
                        "PFTR": 0.05,
                        "NegRiskF1": 0.0,
                        "SecondaryIntentF1": 0.7,
                        "ConstraintF1": 0.95,
                        "SuppressedProtocolF1": 0.45,
                        "RiskCandidateF1": 0.75,
                        "num_cases": 90,
                    }
                },
                "num_cases": 90,
            },
            "num_cases": 90,
        },
    )
    _write_json(
        eval_dir / "rair_test_bert-multilabel_summary.json",
        {
            "data": "benchmarks/rair_rag/data/test/rair_test.jsonl",
            "method": "bert-multilabel",
            "metrics": {
                "RouteAcc": 0.88,
                "HRR": 0.91,
                "PFTR": 0.01,
                "NegRiskF1": 0.72,
                "SecondaryIntentF1": 0.52,
                "ConstraintF1": 0.84,
                "SuppressedProtocolF1": 0.4,
                "RiskCandidateF1": 0.73,
                "by_perturbation_type": {},
                "num_cases": 50,
            },
            "num_cases": 50,
        },
    )
    _write_json(
        eval_dir / "rair_test_llm-zero-shot_summary.json",
        {
            "data": "benchmarks/rair_rag/data/test/rair_test.jsonl",
            "method": "llm-zero-shot",
            "metrics": {
                "RouteAcc": 0.82,
                "HRR": 0.88,
                "PFTR": 0.04,
                "NegRiskF1": 0.65,
                "SecondaryIntentF1": 0.48,
                "ConstraintF1": 0.8,
                "SuppressedProtocolF1": 0.35,
                "RiskCandidateF1": 0.7,
                "by_perturbation_type": {},
                "num_cases": 50,
            },
            "num_cases": 50,
        },
    )

    result = export_rair_tables(eval_dir, out_dir)

    assert result["counts"]["main_results"] == 5
    assert result["counts"]["ablation_results"] == 2
    assert result["counts"]["by_perturbation"] >= 4
    main_rows = _read_csv(out_dir / "main_results.csv")
    assert {row["Method"] for row in main_rows} >= {
        "RAIR w/o Negation Modeling",
        "RAIR w/o Multi-Intent Routing",
        "RAIR",
        "BERT-MultiLabel",
    }
    assert next(row for row in main_rows if row["Method"] == "BERT-MultiLabel")[
        "Offline Deployable"
    ] == "Yes"
    assert "SuppressedProtocolF1" in main_rows[0]
    pert_rows = _read_csv(out_dir / "by_perturbation.csv")
    assert {row["Perturbation"] for row in pert_rows} >= {
        "clean_control",
        "negation_conflict",
        "multi_intent",
        "multi_intent_negation",
        "out_of_scope",
    }
    assert any(row["Method"] == "RAIR" for row in pert_rows)
    assert any(row["Method"] == "LLM-ZeroShot" for row in main_rows)
    ablation_rows = _read_csv(out_dir / "ablation_results.csv")
    assert {row["Method"] for row in ablation_rows} == {
        "RAIR w/o Negation Modeling",
        "RAIR w/o Multi-Intent Routing",
    }
    assert (out_dir / "main_results.md").exists()
    assert (out_dir / "by_perturbation.md").exists()
    assert (out_dir / "ablation_results.md").exists()
    assert (out_dir / "error_analysis.md").exists()
