from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.de_pymoo_optimize import (
    HscRagWeightProblem,
    load_de_config,
    run_de_optimization,
)
from experiments.hsc_objective import SearchSpace, compute_fitness


def _write_policy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "manual-test",
                "weights": {
                    "w_vec": 0.32,
                    "w_sparse": 0.16,
                    "w_quality": 0.12,
                    "w_tag": 0.14,
                    "w_risk": 0.18,
                    "w_unsafe": 0.22,
                    "w_redundancy": 0.08,
                },
                "thresholds": {"min_final_score": 0.0},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _mock_evaluator(
    policy_path: str,
    clean_dev_path: str,
    robust_dev_path: str,
    profile: str,
    work_dir: str,
) -> dict[str, float]:
    del clean_dev_path, robust_dev_path, profile, work_dir
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    weights = policy["weights"]
    route_clean = min(1.0, 0.60 + weights["w_tag"])
    route_robust = min(1.0, 0.55 + weights["w_risk"])
    return {
        "route_accuracy_clean": route_clean,
        "route_accuracy_robust": route_robust,
        "evidence_hit_at_3": min(1.0, 0.40 + weights["w_vec"]),
        "high_risk_recall": 0.98,
        "high_risk_miss_rate": 0.02,
        "unsafe_response_rate": 0.0,
        "unsupported_claim_rate": 0.0,
        "protocol_false_trigger_rate": 0.0,
        "protocol_hit_rate": min(1.0, 0.50 + weights["w_sparse"]),
        "robust_consistency": 0.75,
        "p95_latency_ms": 10.0,
    }


def _config(tmp_path: Path) -> dict[str, object]:
    template = tmp_path / "policy_manual.json"
    _write_policy(template)
    return {
        "seed": 42,
        "n_eval": 4,
        "pop_size": 4,
        "variant": "DE/rand/1/bin",
        "CR": 0.7,
        "dither": "vector",
        "jitter": False,
        "latency_budget_ms": 2000,
        "profile": "paper_eval",
        "clean_dev_path": "benchmarks/data/clean_dev.jsonl",
        "robustness_dev_path": "benchmarks/data/robustness_dev.jsonl",
        "search_space_path": "scoring/search_space.json",
        "template_policy_path": str(template),
        "output_policy_path": str(tmp_path / "policy_de.json"),
        "trials_path": str(tmp_path / "de_trials.csv"),
        "best_metrics_path": str(tmp_path / "de_best_metrics.json"),
        "curve_path": str(tmp_path / "de_curve.csv"),
        "work_dir": str(tmp_path / "de_work"),
    }


def test_search_space_loads_and_vector_to_policy():
    space = SearchSpace.load("scoring/search_space.json")
    x = (space.xl + space.xu) / 2.0
    policy = space.vector_to_policy(x, {"thresholds": {}}, version="candidate")

    assert space.names == [
        "w_vec",
        "w_sparse",
        "w_quality",
        "w_tag",
        "w_risk",
        "w_unsafe",
        "w_redundancy",
    ]
    assert policy["version"] == "candidate"
    assert set(policy["weights"]) == set(space.names)


def test_compute_fitness_returns_float():
    value = compute_fitness(
        {
            "route_accuracy_clean": 0.9,
            "route_accuracy_robust": 0.8,
            "evidence_hit_at_5": 0.7,
            "safety_compliance": 1.0,
            "robust_consistency": 0.6,
            "clarification_appropriateness": 0.9,
            "action_correctness": 0.8,
            "high_risk_miss_rate": 0.05,
            "unsafe_response_rate": 0.0,
            "unsupported_claim_rate": 0.0,
            "latency_penalty": 0.0,
        }
    )

    assert isinstance(value, float)
    assert value > 0


def test_hsc_rag_weight_problem_evaluates_once_with_mock(tmp_path):
    config = _config(tmp_path)
    space = SearchSpace.load(config["search_space_path"])
    problem = HscRagWeightProblem(space, config, evaluator=_mock_evaluator)
    out: dict[str, object] = {}

    problem._evaluate((space.xl + space.xu) / 2.0, out)

    assert "F" in out
    assert "G" in out
    assert len(problem.trials) == 1
    assert Path(str(config["trials_path"])).exists()


def test_short_de_run_writes_policy_and_trials_with_mock(tmp_path):
    config = _config(tmp_path)

    result = run_de_optimization(config, evaluator=_mock_evaluator)
    policy = json.loads(Path(str(config["output_policy_path"])).read_text(encoding="utf-8"))

    assert result["n_trials"] >= 1
    assert policy["version"] == "hsc-rag-de-v1"
    assert Path(str(config["trials_path"])).exists()
    assert Path(str(config["best_metrics_path"])).exists()
    assert Path(str(config["curve_path"])).exists()


def test_de_config_rejects_test_sets(tmp_path):
    config_path = tmp_path / "de_bad.yaml"
    config_path.write_text(
        "clean_dev_path: benchmarks/data/clean_test.jsonl\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="test set"):
        load_de_config(config_path)
