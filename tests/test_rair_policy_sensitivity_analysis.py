from __future__ import annotations

import json
from pathlib import Path

from benchmarks.rair_rag.analyze_negation_failures import analyze_negation_failures
from benchmarks.rair_rag.export_policy_table import export_policy_table
from benchmarks.rair_rag.run_sensitivity_eval import run_sensitivity_eval


def test_export_policy_table_writes_parameters(tmp_path: Path) -> None:
    policy = tmp_path / "policy.yaml"
    out_dir = tmp_path / "tables"
    policy.write_text(
        "\n".join(
            [
                "negation_window: 4",
                "negation_penalty: 0.6",
                "confidence_threshold: 0.2",
                "high_risk_boost: 0.08",
                "operational_constraint_weight: 0.15",
                "intent_base_weights:",
                "  respiratory_distress: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = export_policy_table(policy_path=policy, out_dir=out_dir)

    assert result["num_rows"] >= 6
    markdown = (out_dir / "policy_parameters.md").read_text(encoding="utf-8")
    assert "negation_penalty" in markdown
    assert "intent_base_weights.respiratory_distress" in markdown
    assert (out_dir / "policy_parameters.csv").exists()


def test_run_sensitivity_eval_writes_expected_rows(
    tmp_path: Path, monkeypatch
) -> None:
    policy = tmp_path / "policy.yaml"
    data = tmp_path / "data.jsonl"
    out_dir = tmp_path / "sensitivity"
    policy.write_text("negation_penalty: 0.45\nhigh_risk_boost: 0.05\n", encoding="utf-8")
    data.write_text("", encoding="utf-8")

    def fake_evaluate_with_policy(*, data_path, policy):
        negated = ["severe_bleeding_or_shock"] if policy.negation_penalty >= 0.45 else []
        suppressed = ["prot_bleeding_control"] if negated else []
        return {
            "metrics": {
                "num_cases": 2,
                "NegRiskF1": policy.negation_penalty,
                "PFTR": 0.1,
                "HRR": 0.9 + policy.high_risk_boost,
                "RouteAcc": 0.8,
            },
            "predictions": [
                {
                    "id": "x1",
                    "primary_intent": "trauma_or_fracture",
                    "predicted_route": "route_trauma_or_fracture",
                    "protocol_id": "prot_injury_fracture",
                    "negated_risks": negated,
                    "suppressed_protocols": suppressed,
                    "risk_score": policy.high_risk_boost,
                    "trace": {
                        "negation_trace": [
                            {"negation_probability": policy.negation_penalty}
                        ]
                    },
                },
                {
                    "id": "x2",
                    "primary_intent": (
                        "respiratory_distress"
                        if policy.high_risk_boost >= 1.0
                        else "trauma_or_fracture"
                    ),
                    "predicted_route": "route_respiratory_distress",
                    "protocol_id": "prot_respiratory_distress",
                    "negated_risks": [],
                    "suppressed_protocols": [],
                    "risk_score": policy.high_risk_boost,
                    "trace": {
                        "negation_trace": [
                            {"negation_probability": policy.negation_penalty}
                        ]
                    },
                },
            ],
        }

    monkeypatch.setattr(
        "benchmarks.rair_rag.run_sensitivity_eval._evaluate_with_policy",
        fake_evaluate_with_policy,
    )

    result = run_sensitivity_eval(data_path=data, policy_path=policy, out_dir=out_dir)

    assert result["num_rows"] == 11
    csv_text = (out_dir / "routing_sensitivity.csv").read_text(encoding="utf-8")
    assert "negation_penalty,0.0000,2,0.0000" in csv_text
    assert "negation_penalty,10.0000,2,10.0000" in csv_text
    assert "high_risk_boost,10.0000,2" in csv_text
    assert "primary_intent_changed_count" in csv_text
    markdown = (out_dir / "routing_sensitivity.md").read_text(encoding="utf-8")
    assert "decision path" in markdown
    assert "avg_negation_probability_delta" in markdown


def test_analyze_negation_failures_reports_mismatches(tmp_path: Path) -> None:
    data = tmp_path / "cases.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    out = tmp_path / "negation_failures.md"
    data.write_text(json.dumps(_case(), ensure_ascii=False) + "\n", encoding="utf-8")
    predictions.write_text(
        json.dumps(
            {
                "id": "neg_1",
                "negated_risks": [],
                "risk_candidates": [
                    {"risk": "severe_bleeding_or_shock", "negated": False}
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = analyze_negation_failures(
        data_path=data,
        predictions_path=predictions,
        out_path=out,
        limit=20,
    )

    assert result["total_failures"] == 1
    text = out.read_text(encoding="utf-8")
    assert "negation_scope_missed" in text
    assert "preliminary rule-based" in text


def _case() -> dict[str, object]:
    return {
        "id": "neg_1",
        "canonical_id": "case_neg_1",
        "raw_input": "腿疼但是没流血",
        "canonical_input": "腿疼但是没流血",
        "language": "zh-CN",
        "source_type": "unit_test",
        "guideline_refs": [],
        "perturbation_types": ["negation_conflict"],
        "risk_mentions": [],
        "risk_candidates": [],
        "positive_risks": ["trauma_or_fracture"],
        "negated_risks": ["severe_bleeding_or_shock"],
        "primary_intent": "trauma_or_fracture",
        "secondary_intents": [],
        "operational_constraints": [],
        "expected_route": "route_trauma_or_fracture",
        "expected_protocol_id": "prot_injury_fracture",
        "should_not_trigger": ["prot_bleeding_control"],
        "suppressed_protocols": ["prot_bleeding_control"],
        "safety_boundaries": [],
        "risk_level": "medium",
        "expected_tags": [],
        "label_status": "unit_test",
    }
