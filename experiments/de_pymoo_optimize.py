from __future__ import annotations

import argparse
import csv
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.core.problem import ElementwiseProblem
from pymoo.operators.sampling.lhs import LHS
from pymoo.optimize import minimize

from app.config import PROJECT_ROOT
from benchmarks.run_eval import run_eval
from experiments.hsc_objective import SearchSpace, compute_fitness

Evaluator = Callable[[str, str, str, str, str], dict[str, float]]


DEFAULT_CONFIG = {
    "seed": 42,
    "n_eval": 160,
    "pop_size": 32,
    "variant": "DE/rand/1/bin",
    "CR": 0.7,
    "dither": "vector",
    "jitter": False,
    "latency_budget_ms": 2000,
    "profile": "paper_eval",
    "method": "hsc-rag-de",
    "clean_dev_path": "benchmarks/data/clean_dev.jsonl",
    "robustness_dev_path": "benchmarks/data/robustness_dev.jsonl",
    "search_space_path": "scoring/search_space.json",
    "template_policy_path": "scoring/policy_manual.json",
    "output_policy_path": "scoring/policy_de.json",
    "trials_path": "build/eval/de_trials.csv",
    "best_metrics_path": "build/eval/de_best_metrics.json",
    "curve_path": "build/eval/de_curve.csv",
    "work_dir": "build/eval/de",
}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(_resolve(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, obj: dict[str, Any]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_de_config(path: str | Path) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    p = _resolve(path)
    if p.exists():
        loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"invalid DE config: {p}")
        cfg.update(loaded)
    _validate_dev_dataset("clean_dev_path", str(cfg["clean_dev_path"]))
    _validate_dev_dataset("robustness_dev_path", str(cfg["robustness_dev_path"]))
    return cfg


def _validate_dev_dataset(name: str, path: str) -> None:
    normalized = path.replace("\\", "/").lower()
    if "test" in normalized:
        raise ValueError(f"{name} must not point to a test set: {path}")


def _append_csv_row(path: str | Path, row: dict[str, Any]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(row.keys())
    exists = out.exists() and out.stat().st_size > 0
    with out.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _write_curve(path: str | Path, trials: list[dict[str, Any]]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    best = float("-inf")
    rows = []
    for row in trials:
        fitness = float(row.get("fitness", 0.0))
        best = max(best, fitness)
        rows.append({"eval_id": row["eval_id"], "fitness": fitness, "best_fitness": best})
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["eval_id", "fitness", "best_fitness"])
        writer.writeheader()
        writer.writerows(rows)


def _summary(result: dict[str, Any]) -> dict[str, float]:
    summary = result.get("summary", result)
    return {key: float(value) for key, value in summary.items() if _is_number(value)}


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def default_evaluator(
    policy_path: str,
    clean_dev_path: str,
    robust_dev_path: str,
    profile: str,
    work_dir: str,
) -> dict[str, float]:
    clean = run_eval(
        data=clean_dev_path,
        method="hsc-rag-de",
        policy=policy_path,
        profile=profile,
        out=_resolve(work_dir) / "predictions" / "clean_predictions.jsonl",
        summary=_resolve(work_dir) / "summaries" / "clean_summary.csv",
    )
    robust = run_eval(
        data=robust_dev_path,
        method="hsc-rag-de",
        policy=policy_path,
        profile=profile,
        out=_resolve(work_dir) / "predictions" / "robust_predictions.jsonl",
        summary=_resolve(work_dir) / "summaries" / "robust_summary.csv",
    )
    return merge_dev_metrics(_summary(clean), _summary(robust))


def merge_dev_metrics(clean: dict[str, float], robust: dict[str, float]) -> dict[str, float]:
    high_risk_recall = min(
        clean.get("high_risk_recall", 0.0),
        robust.get("high_risk_recall", 0.0),
    )
    return {
        "route_accuracy_clean": clean.get("route_accuracy", 0.0),
        "route_accuracy_robust": robust.get("route_accuracy", 0.0),
        "evidence_hit_at_3": (
            clean.get("evidence_hit_at_3", 0.0)
            + robust.get("evidence_hit_at_3", 0.0)
        )
        / 2.0,
        "high_risk_recall": high_risk_recall,
        "high_risk_miss_rate": 1.0 - high_risk_recall,
        "unsafe_response_rate": max(
            clean.get("unsafe_response_rate", 0.0),
            robust.get("unsafe_response_rate", 0.0),
        ),
        "unsupported_claim_rate": max(
            clean.get("unsupported_claim_rate", 0.0),
            robust.get("unsupported_claim_rate", 0.0),
        ),
        "protocol_false_trigger_rate": max(
            clean.get("protocol_false_trigger_rate", 0.0),
            robust.get("protocol_false_trigger_rate", 0.0),
        ),
        "protocol_hit_rate": (
            clean.get("protocol_hit_rate", 0.0) + robust.get("protocol_hit_rate", 0.0)
        )
        / 2.0,
        "robust_consistency": robust.get("robust_consistency", 0.0),
        "p95_latency_ms": max(
            clean.get("p95_latency_ms", 0.0),
            robust.get("p95_latency_ms", 0.0),
        ),
    }


class HscRagWeightProblem(ElementwiseProblem):
    def __init__(
        self,
        search_space: SearchSpace,
        config: dict[str, Any],
        evaluator: Evaluator | None = None,
    ) -> None:
        self.search_space = search_space
        self.config = dict(config)
        self.evaluator = evaluator or default_evaluator
        self.template_policy = _load_json(self.config["template_policy_path"])
        self.eval_id = 0
        self.trials: list[dict[str, Any]] = []
        self.best_trial: dict[str, Any] | None = None
        super().__init__(
            n_var=len(search_space.variables),
            n_obj=1,
            n_ieq_constr=4,
            xl=search_space.xl,
            xu=search_space.xu,
        )

    @property
    def latency_budget_ms(self) -> float:
        return float(self.config.get("latency_budget_ms", 2000))

    def _candidate_policy_path(self, eval_id: int) -> Path:
        return (
            _resolve(self.config.get("work_dir", "build/eval/de"))
            / "candidates"
            / f"policy_eval_{eval_id:04d}.json"
        )

    def _evaluate(self, x: Any, out: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self.eval_id += 1
        eval_id = self.eval_id
        weights = self.search_space.vector_to_weights(x)
        policy_path = self._candidate_policy_path(eval_id)
        policy = self.search_space.vector_to_policy(
            x,
            self.template_policy,
            metadata={"eval_id": eval_id, "created_at": datetime.now(UTC).isoformat()},
        )
        _write_json(policy_path, policy)

        try:
            metrics = self.evaluator(
                str(policy_path),
                str(self.config["clean_dev_path"]),
                str(self.config["robustness_dev_path"]),
                str(self.config.get("profile", "paper_eval")),
                str(_resolve(self.config.get("work_dir", "build/eval/de"))),
            )
            metrics = dict(metrics)
            metrics["latency_penalty"] = max(
                0.0,
                (float(metrics.get("p95_latency_ms", 0.0)) - self.latency_budget_ms)
                / max(1.0, self.latency_budget_ms),
            )
            fitness = compute_fitness(metrics)
            constraints = self._constraints(metrics)
            error = ""
        except Exception as exc:
            metrics = {}
            fitness = -1.0
            constraints = [1.0, 1.0, 1.0, 1.0]
            error = str(exc)

        violation = float(sum(max(0.0, value) for value in constraints))
        row = self._trial_row(eval_id, weights, fitness, metrics, violation, error)
        self.trials.append(row)
        _append_csv_row(self.config["trials_path"], row)

        if error == "" and (
            self.best_trial is None or fitness > float(self.best_trial["fitness"])
        ):
            self.best_trial = row

        out["F"] = -float(fitness)
        out["G"] = constraints

    def _constraints(self, metrics: dict[str, Any]) -> list[float]:
        return [
            0.95 - float(metrics.get("high_risk_recall", 0.0)),
            float(metrics.get("unsafe_response_rate", 0.0)) - 0.05,
            float(metrics.get("protocol_false_trigger_rate", 0.0)) - 0.05,
            float(metrics.get("p95_latency_ms", 0.0)) - self.latency_budget_ms,
        ]

    def _trial_row(
        self,
        eval_id: int,
        weights: dict[str, float],
        fitness: float,
        metrics: dict[str, Any],
        violation: float,
        error: str,
    ) -> dict[str, Any]:
        return {
            "eval_id": eval_id,
            "weights": json.dumps(weights, ensure_ascii=False, sort_keys=True),
            "fitness": fitness,
            "route_accuracy_clean": metrics.get("route_accuracy_clean", 0.0),
            "route_accuracy_robust": metrics.get("route_accuracy_robust", 0.0),
            "high_risk_recall": metrics.get("high_risk_recall", 0.0),
            "unsafe_response_rate": metrics.get("unsafe_response_rate", 0.0),
            "unsupported_claim_rate": metrics.get("unsupported_claim_rate", 0.0),
            "p95_latency_ms": metrics.get("p95_latency_ms", 0.0),
            "constraint_violation": violation,
            "error": error,
        }


def _build_algorithm(config: dict[str, Any]) -> DE:
    return DE(
        pop_size=int(config["pop_size"]),
        sampling=LHS(),
        variant=str(config["variant"]),
        CR=float(config["CR"]),
        dither=config["dither"],
        jitter=bool(config["jitter"]),
    )


def _write_best_outputs(
    problem: HscRagWeightProblem,
    config: dict[str, Any],
    result_x: Any,
) -> None:
    best = problem.best_trial
    if best is None:
        weights = problem.search_space.vector_to_weights(result_x)
        best_fitness = None
    else:
        weights = json.loads(str(best["weights"]))
        best_fitness = float(best["fitness"])

    output_policy = problem.search_space.vector_to_policy(
        [weights[name] for name in problem.search_space.names],
        problem.template_policy,
        version="hsc-rag-de-v1",
        metadata={
            "seed": int(config["seed"]),
            "n_eval": int(config["n_eval"]),
            "best_fitness": best_fitness,
            "dev_datasets": [
                str(config["clean_dev_path"]),
                str(config["robustness_dev_path"]),
            ],
            "optimizer": "pymoo.DE",
        },
    )
    _write_json(config["output_policy_path"], output_policy)
    _write_json(
        config["best_metrics_path"],
        {
            "created_at": datetime.now(UTC).isoformat(),
            "best_trial": best or {},
            "output_policy_path": str(config["output_policy_path"]),
        },
    )
    _write_curve(config["curve_path"], problem.trials)


def run_de_optimization(
    config: dict[str, Any],
    evaluator: Evaluator | None = None,
) -> dict[str, Any]:
    os.environ["RUNTIME_PROFILE"] = str(config.get("profile", "paper_eval"))
    search_space = SearchSpace.load(config["search_space_path"])
    problem = HscRagWeightProblem(search_space, config, evaluator=evaluator)
    algorithm = _build_algorithm(config)
    result = minimize(
        problem,
        algorithm,
        ("n_eval", int(config["n_eval"])),
        seed=int(config["seed"]),
        verbose=False,
        save_history=False,
    )
    _write_best_outputs(problem, config, result.X)
    return {
        "best_fitness": None
        if problem.best_trial is None
        else float(problem.best_trial["fitness"]),
        "n_trials": len(problem.trials),
        "output_policy_path": str(config["output_policy_path"]),
        "trials_path": str(config["trials_path"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline pymoo DE optimization for HSC-RAG scoring weights."
    )
    parser.add_argument("--config", default="experiments/configs/de_hsc_rag.yaml")
    args = parser.parse_args()

    config = load_de_config(args.config)
    result = run_de_optimization(config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
