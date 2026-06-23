from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from experiments.de_pymoo_optimize import (
    HscRagWeightProblem,
    load_de_config,
    merge_dev_metrics,
    run_de_optimization,
)
from experiments.hsc_objective import SearchSpace, compute_fitness


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _search_space_path(tmp_path: Path) -> Path:
    path = tmp_path / "search_space.json"
    _write_json(
        path,
        {
            "version": "test-search-space",
            "weights": {
                "w_vec": {"low": 0.1, "high": 0.5},
                "w_risk": {"low": 0.0, "high": 0.4},
            },
        },
    )
    return path


def _template_policy_path(tmp_path: Path) -> Path:
    path = tmp_path / "policy_manual.json"
    _write_json(
        path,
        {
            "version": "manual-test",
            "weights": {"w_vec": 0.2, "w_risk": 0.1},
            "thresholds": {"unsafe_soft_penalty": 0.35},
            "metadata": {"source": "template"},
        },
    )
    return path


def _config(tmp_path: Path) -> dict:
    return {
        "seed": 1,
        "n_eval": 4,
        "pop_size": 4,
        "variant": "DE/rand/1/bin",
        "CR": 0.7,
        "dither": "vector",
        "jitter": False,
        "latency_budget_ms": 2000,
        "profile": "paper_eval",
        "method": "hsc-rag-de",
        "clean_dev_path": str(tmp_path / "clean_dev.jsonl"),
        "robustness_dev_path": str(tmp_path / "robustness_dev.jsonl"),
        "search_space_path": str(_search_space_path(tmp_path)),
        "template_policy_path": str(_template_policy_path(tmp_path)),
        "output_policy_path": str(tmp_path / "policy_de.json"),
        "trials_path": str(tmp_path / "de_trials.csv"),
        "best_metrics_path": str(tmp_path / "de_best_metrics.json"),
        "curve_path": str(tmp_path / "de_curve.csv"),
        "work_dir": str(tmp_path / "de_work"),
    }


def _metrics(**overrides) -> dict[str, float]:
    metrics = {
        "route_accuracy_clean": 0.8,
        "route_accuracy_robust": 0.7,
        "evidence_hit_at_3": 0.6,
        "high_risk_recall": 0.96,
        "high_risk_miss_rate": 0.04,
        "unsafe_response_rate": 0.01,
        "unsupported_claim_rate": 0.02,
        "protocol_false_trigger_rate": 0.01,
        "protocol_hit_rate": 0.7,
        "robust_consistency": 0.8,
        "p95_latency_ms": 100.0,
        "latency_penalty": 0.0,
    }
    metrics.update(overrides)
    return metrics


def test_search_space_loads_and_clips_weights(tmp_path):
    space = SearchSpace.load(_search_space_path(tmp_path))

    assert space.version == "test-search-space"
    assert space.names == ["w_vec", "w_risk"]
    assert space.vector_to_weights([-1.0, 2.0]) == {"w_vec": 0.1, "w_risk": 0.4}


def test_vector_to_policy_preserves_thresholds_and_writes_metadata(tmp_path):
    space = SearchSpace.load(_search_space_path(tmp_path))
    template = json.loads(_template_policy_path(tmp_path).read_text(encoding="utf-8"))

    policy = space.vector_to_policy(
        [0.3, 0.2], template, version="candidate-v1", metadata={"eval_id": 3}
    )

    assert policy["version"] == "candidate-v1"
    assert policy["weights"] == {"w_vec": 0.3, "w_risk": 0.2}
    assert policy["thresholds"] == {"unsafe_soft_penalty": 0.35}
    assert policy["metadata"] == {"eval_id": 3}


def test_compute_fitness_rewards_quality_and_penalizes_risk():
    good = compute_fitness(_metrics())
    better = compute_fitness(
        _metrics(
            route_accuracy_clean=0.95,
            route_accuracy_robust=0.9,
            evidence_hit_at_3=0.85,
            high_risk_recall=0.99,
            high_risk_miss_rate=0.01,
            unsafe_response_rate=0.0,
            unsupported_claim_rate=0.0,
            latency_penalty=0.0,
        )
    )
    worse = compute_fitness(
        _metrics(
            unsafe_response_rate=0.2,
            unsupported_claim_rate=0.2,
            high_risk_miss_rate=0.3,
            latency_penalty=0.5,
        )
    )

    assert better > good
    assert worse < good


def test_load_de_config_loads_yaml_and_rejects_test_paths(tmp_path):
    config_path = tmp_path / "de.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "seed": 7,
                "n_eval": 4,
                "clean_dev_path": "benchmarks/data/clean_dev.jsonl",
                "robustness_dev_path": "benchmarks/data/robustness_dev.jsonl",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    loaded = load_de_config(config_path)
    assert loaded["seed"] == 7
    assert loaded["n_eval"] == 4

    bad_config_path = tmp_path / "de_bad.yaml"
    bad_config_path.write_text(
        yaml.safe_dump(
            {
                "clean_dev_path": "benchmarks/data/final_test.jsonl",
                "robustness_dev_path": "benchmarks/data/robustness_dev.jsonl",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="test set"):
        load_de_config(bad_config_path)


def test_merge_dev_metrics_uses_min_for_recall_and_max_for_penalties():
    merged = merge_dev_metrics(
        {
            "route_accuracy": 0.9,
            "evidence_hit_at_3": 0.8,
            "high_risk_recall": 0.98,
            "unsafe_response_rate": 0.01,
            "unsupported_claim_rate": 0.02,
            "protocol_false_trigger_rate": 0.03,
            "protocol_hit_rate": 0.8,
            "p95_latency_ms": 100.0,
        },
        {
            "route_accuracy": 0.7,
            "evidence_hit_at_3": 0.6,
            "high_risk_recall": 0.9,
            "unsafe_response_rate": 0.04,
            "unsupported_claim_rate": 0.05,
            "protocol_false_trigger_rate": 0.02,
            "protocol_hit_rate": 0.6,
            "robust_consistency": 0.75,
            "p95_latency_ms": 300.0,
        },
    )

    assert merged["route_accuracy_clean"] == 0.9
    assert merged["route_accuracy_robust"] == 0.7
    assert merged["evidence_hit_at_3"] == pytest.approx(0.7)
    assert merged["high_risk_recall"] == 0.9
    assert merged["unsafe_response_rate"] == 0.04
    assert merged["unsupported_claim_rate"] == 0.05
    assert merged["protocol_false_trigger_rate"] == 0.03
    assert merged["p95_latency_ms"] == 300.0


def test_problem_evaluate_writes_candidate_policy_and_trial_rows(tmp_path):
    config = _config(tmp_path)
    space = SearchSpace.load(config["search_space_path"])

    def evaluator(policy_path, clean_dev_path, robust_dev_path, profile, work_dir):
        assert Path(policy_path).exists()
        assert clean_dev_path == config["clean_dev_path"]
        assert robust_dev_path == config["robustness_dev_path"]
        assert profile == "paper_eval"
        assert Path(work_dir) == Path(config["work_dir"])
        return _metrics()

    problem = HscRagWeightProblem(space, config, evaluator=evaluator)
    out: dict = {}
    problem._evaluate([0.3, 0.2], out)

    candidate = Path(config["work_dir"]) / "candidates" / "policy_eval_0001.json"
    with Path(config["trials_path"]).open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert candidate.exists()
    assert out["F"] < 0
    assert out["G"] == pytest.approx([-0.01, -0.04, -0.04, -1900.0])
    assert len(rows) == 1
    assert float(rows[0]["fitness"]) > 0
    assert json.loads(rows[0]["weights"]) == {"w_vec": 0.3, "w_risk": 0.2}
    assert "constraint_violation" in rows[0]
    assert rows[0]["error"] == ""


def test_problem_evaluate_records_error_when_evaluator_fails(tmp_path):
    config = _config(tmp_path)
    space = SearchSpace.load(config["search_space_path"])

    def evaluator(*args):
        raise RuntimeError("fake evaluator failure")

    problem = HscRagWeightProblem(space, config, evaluator=evaluator)
    out: dict = {}
    problem._evaluate([0.3, 0.2], out)

    with Path(config["trials_path"]).open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert out["F"] == 1.0
    assert rows[0]["fitness"] == "-1.0"
    assert "fake evaluator failure" in rows[0]["error"]


def test_run_de_optimization_writes_policy_trials_curve_and_best_metrics(tmp_path):
    config = _config(tmp_path)

    def evaluator(policy_path, clean_dev_path, robust_dev_path, profile, work_dir):
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        weights = policy["weights"]
        route = 0.6 + 0.2 * weights["w_vec"] + 0.1 * weights["w_risk"]
        return _metrics(
            route_accuracy_clean=route,
            route_accuracy_robust=route - 0.05,
            evidence_hit_at_3=0.5 + 0.1 * weights["w_risk"],
        )

    result = run_de_optimization(config, evaluator=evaluator)

    output_policy = json.loads(
        Path(config["output_policy_path"]).read_text(encoding="utf-8")
    )
    best_metrics = json.loads(
        Path(config["best_metrics_path"]).read_text(encoding="utf-8")
    )
    assert Path(config["output_policy_path"]).exists()
    assert Path(config["trials_path"]).exists()
    assert Path(config["best_metrics_path"]).exists()
    assert Path(config["curve_path"]).exists()
    assert result["n_trials"] >= 1
    assert output_policy["metadata"]["optimizer"] == "pymoo.DE"
    assert output_policy["metadata"]["seed"] == 1
    assert output_policy["metadata"]["n_eval"] == 4
    assert output_policy["metadata"]["dev_datasets"] == [
        config["clean_dev_path"],
        config["robustness_dev_path"],
    ]
    assert output_policy["metadata"]["best_fitness"] == result["best_fitness"]
    assert best_metrics["output_policy_path"] == config["output_policy_path"]
    assert "best_trial" in best_metrics
