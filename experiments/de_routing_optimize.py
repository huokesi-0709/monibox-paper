from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from benchmarks.rair_rag.run_routing_eval import evaluate_routing_cases
from runtime.multi_intent_router import DEFAULT_INTENT_WEIGHTS
from runtime.routing_policy import RoutingPolicy

try:
    from pymoo.algorithms.soo.nonconvex.de import DE
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.operators.sampling.lhs import LHS
    from pymoo.optimize import minimize
except ImportError as exc:  # pragma: no cover - exercised by optional envs
    raise SystemExit(
        "pymoo is required for RAIR routing DE. "
        "Install paper extras with: uv sync --extra paper"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_DATA_PATH = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "dev" / "rair_dev.jsonl"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "experiments" / "configs" / "de_routing.yaml"

OBJECTIVE_WEIGHTS = {
    "RouteAcc": 0.35,
    "HRR": 0.30,
    "NegRiskF1": 0.15,
    "SecondaryIntentF1": 0.10,
    "PFTR": -0.25,
}
PFTR_MAX = 0.05
HRR_MIN = 0.85

DEFAULT_CONFIG: dict[str, Any] = {
    "seed": 42,
    "n_eval": 120,
    "pop_size": 24,
    "variant": "DE/rand/1/bin",
    "CR": 0.7,
    "dither": "vector",
    "jitter": False,
    "verbose": False,
    "data_path": "benchmarks/rair_rag/data/dev/rair_dev.jsonl",
    "template_policy_path": "scoring/routing_policy_manual.yaml",
    "output_policy_path": "scoring/routing_policy_de.yaml",
    "best_policy_path": "build/rair_eval/de_best_policy.yaml",
    "trials_path": "build/rair_eval/de_trials.jsonl",
    "summary_path": "build/rair_eval/de_summary.json",
    "work_dir": "build/rair_eval/de_routing",
    "bounds": {
        "negation_window": [2, 12],
        "negation_penalty": [0.10, 0.90],
        "confidence_threshold": [0.05, 0.65],
        "high_risk_boost": [0.00, 0.25],
        "operational_constraint_weight": [0.05, 0.50],
        "intent_base_weight": [0.02, 1.20],
    },
}


@dataclass(frozen=True)
class SearchVariable:
    name: str
    lower: float
    upper: float
    intent: str | None = None
    kind: str = "float"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimize RAIR-RAG risk-routing parameters with Differential Evolution."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--n-eval", type=int)
    parser.add_argument("--pop-size", type=int)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.n_eval is not None:
        config["n_eval"] = args.n_eval
    if args.pop_size is not None:
        config["pop_size"] = args.pop_size

    summary = run_de_optimization(config)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def run_de_optimization(config: dict[str, Any]) -> dict[str, Any]:
    validate_dev_data_path(config["data_path"])
    trials_path = resolve_path(config["trials_path"])
    trials_path.parent.mkdir(parents=True, exist_ok=True)
    trials_path.write_text("", encoding="utf-8")

    problem = RoutingPolicyProblem(config)
    baseline_trial = evaluate_policy_candidate(
        config=config,
        policy=problem.template_policy,
        eval_id=0,
        source="manual-baseline",
    )
    problem.trials.append(baseline_trial)
    append_jsonl(config["trials_path"], strip_policy_yaml(baseline_trial))

    algorithm = DE(
        pop_size=int(config["pop_size"]),
        sampling=LHS(),
        variant=str(config["variant"]),
        CR=float(config["CR"]),
        dither=config.get("dither"),
        jitter=bool(config.get("jitter", False)),
    )
    minimize(
        problem,
        algorithm,
        termination=("n_eval", int(config["n_eval"])),
        seed=int(config["seed"]),
        verbose=bool(config.get("verbose", False)),
    )

    best_trial = select_best_trial(problem.trials)
    write_text_file(config["output_policy_path"], best_trial["policy_yaml"])
    write_text_file(config["best_policy_path"], best_trial["policy_yaml"])

    summary = {
        "data_path": str(resolve_path(config["data_path"])),
        "objective": "0.35*RouteAcc + 0.30*HRR + 0.15*NegRiskF1 + "
        "0.10*SecondaryIntentF1 - 0.25*PFTR",
        "constraints": {"PFTR_max": PFTR_MAX, "HRR_min": HRR_MIN},
        "num_trials": len(problem.trials),
        "feasible_trial_found": any(trial["feasible"] for trial in problem.trials),
        "best_trial": strip_policy_yaml(best_trial),
        "output_policy_path": str(resolve_path(config["output_policy_path"])),
        "best_policy_path": str(resolve_path(config["best_policy_path"])),
        "trials_path": str(resolve_path(config["trials_path"])),
    }
    write_json(config["summary_path"], summary)
    return summary


class RoutingPolicyProblem(ElementwiseProblem):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = dict(config)
        self.template_policy = RoutingPolicy.from_file(
            resolve_path(self.config["template_policy_path"])
        )
        self.variables = build_search_variables(self.config)
        self.eval_id = 0
        self.trials: list[dict[str, Any]] = []
        super().__init__(
            n_var=len(self.variables),
            n_obj=1,
            n_ieq_constr=2,
            xl=[variable.lower for variable in self.variables],
            xu=[variable.upper for variable in self.variables],
        )

    def _evaluate(self, x: list[float], out: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        self.eval_id += 1
        policy = self.policy_from_vector(x)
        trial = evaluate_policy_candidate(
            config=self.config,
            policy=policy,
            eval_id=self.eval_id,
            source="de-candidate",
        )
        self.trials.append(trial)
        append_jsonl(self.config["trials_path"], strip_policy_yaml(trial))

        out["F"] = [-float(trial["fitness"])]
        out["G"] = [trial["constraint_pftr"], trial["constraint_hrr"]]

    def policy_from_vector(self, x: list[float]) -> RoutingPolicy:
        data = self.template_policy.to_dict()
        intent_weights = dict(self.template_policy.intent_base_weights)
        for variable, value in zip(self.variables, x, strict=True):
            if variable.intent:
                intent_weights[variable.intent] = round(float(value), 4)
            elif variable.kind == "int":
                data[variable.name] = round(float(value))
            else:
                data[variable.name] = round(float(value), 4)
        data["intent_base_weights"] = intent_weights
        return RoutingPolicy.from_dict(data)


def load_config(path: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    resolved = resolve_path(path)
    if resolved.exists():
        loaded = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"invalid DE routing config: {resolved}")
        config.update(loaded)
        config["bounds"] = {
            **DEFAULT_CONFIG["bounds"],
            **dict(loaded.get("bounds") or {}),
        }
    validate_dev_data_path(config["data_path"])
    return config


def build_search_variables(config: dict[str, Any]) -> list[SearchVariable]:
    bounds = dict(config["bounds"])
    variables = [
        bounded_variable("negation_window", bounds, kind="int"),
        bounded_variable("negation_penalty", bounds),
        bounded_variable("confidence_threshold", bounds),
        bounded_variable("high_risk_boost", bounds),
        bounded_variable("operational_constraint_weight", bounds),
    ]
    lower, upper = parse_bound(bounds["intent_base_weight"], "intent_base_weight")
    variables.extend(
        [
            SearchVariable(
                name=f"intent_base_weights.{intent}",
                lower=lower,
                upper=upper,
                intent=intent,
            )
            for intent in DEFAULT_INTENT_WEIGHTS
        ]
    )
    return variables


def bounded_variable(
    name: str, bounds: dict[str, Any], *, kind: str = "float"
) -> SearchVariable:
    lower, upper = parse_bound(bounds[name], name)
    return SearchVariable(name=name, lower=lower, upper=upper, kind=kind)


def parse_bound(raw: Any, name: str) -> tuple[float, float]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError(f"bounds.{name} must be a two-item list")
    lower, upper = float(raw[0]), float(raw[1])
    if lower >= upper:
        raise ValueError(f"bounds.{name} lower bound must be smaller than upper bound")
    return lower, upper


def compute_fitness(metrics: dict[str, Any]) -> float:
    return round(
        OBJECTIVE_WEIGHTS["RouteAcc"] * float(metrics.get("RouteAcc", 0.0))
        + OBJECTIVE_WEIGHTS["HRR"] * float(metrics.get("HRR", 0.0))
        + OBJECTIVE_WEIGHTS["NegRiskF1"] * float(metrics.get("NegRiskF1", 0.0))
        + OBJECTIVE_WEIGHTS["SecondaryIntentF1"]
        * float(metrics.get("SecondaryIntentF1", 0.0))
        + OBJECTIVE_WEIGHTS["PFTR"] * float(metrics.get("PFTR", 0.0)),
        6,
    )


def evaluate_policy_candidate(
    *,
    config: dict[str, Any],
    policy: RoutingPolicy,
    eval_id: int,
    source: str,
) -> dict[str, Any]:
    policy_yaml = format_policy_yaml(policy, version=f"{source}-{eval_id:04d}")
    candidate_path = candidate_policy_path(config, eval_id)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(policy_yaml, encoding="utf-8")

    summary = evaluate_routing_cases(
        data_path=resolve_path(config["data_path"]),
        method="risk-router-de",
        policy_path=candidate_path,
    )
    metrics = summary["metrics"]
    return {
        "eval_id": eval_id,
        "source": source,
        "fitness": compute_fitness(metrics),
        "feasible": metrics["PFTR"] <= PFTR_MAX and metrics["HRR"] >= HRR_MIN,
        "constraint_pftr": metrics["PFTR"] - PFTR_MAX,
        "constraint_hrr": HRR_MIN - metrics["HRR"],
        "metrics": metrics,
        "candidate_policy_path": str(candidate_path),
        "policy_yaml": policy_yaml,
        "policy": policy.to_dict(),
    }


def select_best_trial(trials: list[dict[str, Any]]) -> dict[str, Any]:
    if not trials:
        raise ValueError("DE produced no trials")
    feasible = [trial for trial in trials if trial["feasible"]]
    candidates = feasible or trials
    return max(
        candidates,
        key=lambda trial: (
            float(trial["fitness"]),
            float(trial["metrics"].get("HRR", 0.0)),
            -float(trial["metrics"].get("PFTR", 1.0)),
        ),
    )


def format_policy_yaml(policy: RoutingPolicy, *, version: str) -> str:
    lines = [
        f'version: "{version}"',
        f"negation_window: {policy.negation_window}",
        f"negation_penalty: {policy.negation_penalty:.4f}",
        f"confidence_threshold: {policy.confidence_threshold:.4f}",
        f"high_risk_boost: {policy.high_risk_boost:.4f}",
        f"operational_constraint_weight: {policy.operational_constraint_weight:.4f}",
        "intent_base_weights:",
    ]
    for intent, weight in policy.intent_base_weights.items():
        lines.append(f"  {intent}: {float(weight):.4f}")
    return "\n".join(lines) + "\n"


def candidate_policy_path(config: dict[str, Any], eval_id: int) -> Path:
    return (
        resolve_path(config["work_dir"])
        / "candidates"
        / f"routing_policy_eval_{eval_id:04d}.yaml"
    )


def predictions_path(config: dict[str, Any], eval_id: int) -> Path:
    return resolve_path(config["work_dir"]) / "scratch_predictions.jsonl"


def eval_summary_path(config: dict[str, Any], eval_id: int) -> Path:
    return resolve_path(config["work_dir"]) / "scratch_summary.json"


def validate_dev_data_path(path: str | Path) -> None:
    resolved = resolve_path(path).resolve()
    if resolved != DEV_DATA_PATH.resolve():
        raise ValueError(
            "DE routing optimization must only read the dev split: "
            "benchmarks/rair_rag/data/dev/rair_dev.jsonl"
        )


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    out = resolve_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    out = resolve_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text_file(path: str | Path, text: str) -> None:
    out = resolve_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def strip_policy_yaml(trial: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in trial.items() if key != "policy_yaml"}


if __name__ == "__main__":
    main()
