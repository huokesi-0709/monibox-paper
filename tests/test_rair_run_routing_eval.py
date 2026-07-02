from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.rair_rag.run_routing_eval import run_routing_eval


def test_run_routing_eval_writes_predictions_and_summary(tmp_path: Path) -> None:
    data = tmp_path / "cases.jsonl"
    out = tmp_path / "predictions.jsonl"
    summary = tmp_path / "summary.json"
    write_jsonl(
        data,
        [
            case(
                item_id="neg_1",
                raw_input="\u6211\u817f\u75bc\uff0c\u4f46\u662f\u6ca1\u6d41\u8840",
                perturbation_types=["negation_conflict"],
                primary_intent="trauma_or_fracture",
                positive_risks=["trauma_or_fracture"],
                negated_risks=["severe_bleeding_or_shock"],
                should_not_trigger=["prot_bleeding_control"],
                expected_route="route_trauma_or_fracture",
                risk_level="medium",
            ),
            case(
                item_id="multi_1",
                raw_input="\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u624b\u673a\u5feb\u6ca1\u7535\u4e86",
                perturbation_types=["multi_intent"],
                primary_intent="respiratory_distress",
                positive_risks=["respiratory_distress"],
                operational_constraints=["low_battery"],
                expected_route="route_respiratory_distress",
                risk_level="critical",
            ),
        ],
    )

    result = run_routing_eval(
        data_path=data,
        method="risk-router",
        policy_path=None,
        out_path=out,
        summary_path=summary,
    )

    predictions = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    assert result["num_cases"] == 2
    assert summary_data["method"] == "risk-router"
    assert predictions[0]["primary_intent"] == "trauma_or_fracture"
    assert predictions[0]["negated_risks"] == ["severe_bleeding_or_shock"]
    assert predictions[0]["protocol_id"] == "prot_injury_fracture"
    assert predictions[0]["suppressed_protocols"] == ["prot_bleeding_control"]
    assert predictions[0]["risk_candidates"]
    assert predictions[0]["risk_context"]["predicted_route"] == "route_trauma_or_fracture"
    assert predictions[0]["risk_context"]["suppressed_protocols"] == [
        "prot_bleeding_control"
    ]
    assert predictions[1]["primary_intent"] == "respiratory_distress"
    assert predictions[1]["operational_constraints"] == ["low_battery"]
    assert predictions[1]["risk_context"]["primary_intent"] == "respiratory_distress"
    assert "risk_candidates" in predictions[1]["risk_context"]
    assert summary_data["metrics"]["PFTR"] == 0.0
    assert "negation_conflict" in summary_data["metrics"]["by_perturbation_type"]


def test_run_routing_eval_supports_policy_and_baselines(tmp_path: Path) -> None:
    data = tmp_path / "cases.jsonl"
    policy = tmp_path / "policy.json"
    write_jsonl(
        data,
        [
            case(
                item_id="multi_1",
                raw_input="\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u4e5f\u5f88\u5bb3\u6015",
                perturbation_types=["multi_intent"],
                primary_intent="psychological_distress",
                positive_risks=["psychological_distress", "respiratory_distress"],
                secondary_intents=["respiratory_distress"],
                expected_route="route_psychological_support",
                risk_level="medium",
            )
        ],
    )
    policy.write_text(
        json.dumps(
            {
                "intent_base_weights": {
                    "psychological_distress": 1.2,
                    "respiratory_distress": 0.4,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    for method in [
        "keyword-baseline",
        "no-negation",
        "single-intent",
        "risk-router-de",
    ]:
        result = run_routing_eval(
            data_path=data,
            method=method,
            policy_path=policy if method == "risk-router-de" else None,
            out_path=tmp_path / f"{method}.jsonl",
            summary_path=tmp_path / f"{method}.json",
        )
        assert result["num_cases"] == 1
        assert "metrics" in result

    prediction = json.loads((tmp_path / "risk-router-de.jsonl").read_text(encoding="utf-8"))
    assert prediction["primary_intent"] == "psychological_distress"
    assert "risk_context" in prediction
    assert prediction["risk_context"]["primary_intent"] == "psychological_distress"


def test_candidate_multilabel_is_proxy_baseline(tmp_path: Path) -> None:
    data = tmp_path / "cases.jsonl"
    write_jsonl(
        data,
        [
            case(
                item_id="multi_1",
                raw_input="\u6211\u5598\u4e0d\u4e0a\u6c14\uff0c\u624b\u673a\u5feb\u6ca1\u7535\u4e86",
                perturbation_types=["multi_intent"],
                primary_intent="respiratory_distress",
                positive_risks=["respiratory_distress"],
                operational_constraints=["low_battery"],
                expected_route="route_respiratory_distress",
                risk_level="critical",
            )
        ],
    )

    result = run_routing_eval(
        data_path=data,
        method="candidate-multilabel",
        policy_path=None,
        out_path=tmp_path / "candidate.jsonl",
        summary_path=tmp_path / "candidate.json",
    )

    prediction = json.loads((tmp_path / "candidate.jsonl").read_text(encoding="utf-8"))
    assert result["method"] == "candidate-multilabel"
    assert prediction["method"] == "candidate-multilabel"
    assert "candidate-multilabel local proxy" in prediction["trace"]["baseline"]


def test_bert_multilabel_requires_trained_model(tmp_path: Path) -> None:
    data = tmp_path / "cases.jsonl"
    write_jsonl(
        data,
        [
            case(
                item_id="clean_1",
                raw_input="\u6211\u5598\u4e0d\u4e0a\u6c14",
                perturbation_types=["clean_control"],
                primary_intent="respiratory_distress",
                positive_risks=["respiratory_distress"],
                expected_route="route_respiratory_distress",
                risk_level="critical",
            )
        ],
    )

    with pytest.raises(FileNotFoundError, match="Train it first"):
        run_routing_eval(
            data_path=data,
            method="bert-multilabel",
            policy_path=None,
            out_path=tmp_path / "bert.jsonl",
            summary_path=tmp_path / "bert.json",
            bert_model_dir=tmp_path / "missing_best_model",
        )


def case(
    *,
    item_id: str,
    raw_input: str,
    perturbation_types: list[str],
    primary_intent: str,
    positive_risks: list[str],
    expected_route: str,
    risk_level: str,
    negated_risks: list[str] | None = None,
    secondary_intents: list[str] | None = None,
    operational_constraints: list[str] | None = None,
    should_not_trigger: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": item_id,
        "canonical_id": f"case_{item_id}",
        "raw_input": raw_input,
        "canonical_input": raw_input,
        "language": "zh-CN",
        "source_type": "unit_test",
        "guideline_refs": [],
        "perturbation_types": perturbation_types,
        "risk_mentions": [],
        "positive_risks": positive_risks,
        "negated_risks": negated_risks or [],
        "primary_intent": primary_intent,
        "secondary_intents": secondary_intents or [],
        "operational_constraints": operational_constraints or [],
        "expected_route": expected_route,
        "expected_protocol_id": None,
        "should_not_trigger": should_not_trigger or [],
        "risk_level": risk_level,
        "expected_tags": [],
        "safety_note": None,
        "reference_reply": None,
        "label_status": "unit_test",
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
