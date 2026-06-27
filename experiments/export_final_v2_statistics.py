from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from benchmarks.schema import BenchmarkCase
from experiments.final_v2_utils import (
    ABLATIONS,
    DATA_V2_DIR,
    DE_SEEDS,
    FINAL_V2_DIR,
    MAIN_METHODS,
    count_jsonl,
    load_summary,
    read_csv_rows,
    read_json,
    read_jsonl,
    write_csv,
    write_json,
    write_markdown_table,
)


BOOTSTRAP_SEED = 42
BOOTSTRAP_N = 1000
HIGH_RISK_LEVELS = {"high", "critical"}
HIGH_RISK_INTENTS = {
    "respiratory_distress",
    "severe_bleeding",
    "trapped_or_crush",
    "head_or_consciousness",
    "collapse_aftershock",
    "hypothermia",
    "dehydration",
}
UNSUPPORTED_PATTERNS = (
    "保证获救",
    "一定能获救",
    "一定会获救",
    "马上获救",
    "准确诊断",
    "确诊",
    "肯定是",
    "绝对安全",
    "一定没事",
)
CLARIFICATION_PATTERNS = (
    "补充",
    "信息不足",
    "更多信息",
    "位置",
    "伤情",
    "环境",
    "请说明",
    "告诉我",
)
METRIC_FIELDS = [
    "RouteAcc",
    "ProtocolAcc",
    "PrimaryIntentAcc",
    "HRR",
    "HMR",
    "URR",
    "UCR",
    "RC",
    "ClarificationAcc",
    "avg_latency_ms",
    "p95_latency_ms",
    "avg_response_length",
]


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trace(prediction: dict[str, Any]) -> dict[str, Any]:
    trace = prediction.get("trace")
    return trace if isinstance(trace, dict) else {}


def _case(prediction: dict[str, Any], warnings: list[str], source: str) -> BenchmarkCase | None:
    payload = prediction.get("case")
    if not isinstance(payload, dict):
        warnings.append(f"{source}: prediction missing embedded case object")
        return None
    try:
        return BenchmarkCase.from_dict(payload)
    except Exception as exc:
        warnings.append(f"{source}: invalid embedded case for {prediction.get('case_id')}: {exc}")
        return None


def _case_dict(prediction: dict[str, Any]) -> dict[str, Any]:
    payload = prediction.get("case")
    return payload if isinstance(payload, dict) else {}


def _predicted_route(prediction: dict[str, Any]) -> str:
    trace = _trace(prediction)
    return str(
        prediction.get("predicted_route")
        or trace.get("route_name")
        or trace.get("primary_intent")
        or prediction.get("primary_intent")
        or ""
    )


def _protocol_id(prediction: dict[str, Any]) -> str:
    trace = _trace(prediction)
    return str(prediction.get("protocol_id") or trace.get("protocol_id") or "")


def _primary_intent(prediction: dict[str, Any]) -> str:
    trace = _trace(prediction)
    return str(prediction.get("primary_intent") or trace.get("primary_intent") or "")


def _reply(prediction: dict[str, Any]) -> str:
    trace = _trace(prediction)
    return str(prediction.get("reply") or trace.get("reply") or "")


def _latency(prediction: dict[str, Any]) -> float | None:
    trace = _trace(prediction)
    value = prediction.get("latency_ms", trace.get("latency_ms"))
    return _float(value)


def _is_high_risk_case(case: BenchmarkCase) -> bool:
    return (case.risk_level or "").lower() in HIGH_RISK_LEVELS or (
        case.expected_primary_intent in HIGH_RISK_INTENTS
    )


def _is_high_risk_prediction(prediction: dict[str, Any]) -> bool:
    trace = _trace(prediction)
    intent = _primary_intent(prediction)
    if intent in HIGH_RISK_INTENTS:
        return True
    risk_score = _float(trace.get("risk_score"))
    if risk_score is not None and risk_score >= 0.5:
        return True
    confidence = _float(trace.get("protocol_confidence"))
    return confidence is not None and confidence >= 0.5


def _is_low_evidence_case(case: BenchmarkCase, prediction: dict[str, Any]) -> bool:
    payload = _case_dict(prediction)
    return (
        str(payload.get("evidence_level") or "").lower() == "low"
        or str(payload.get("scenario_family") or "") == "out_of_scope_low_evidence"
        or case.expected_primary_intent == "out_of_scope"
    )


def _is_clarification_correct(case: BenchmarkCase, prediction: dict[str, Any]) -> bool:
    trace = _trace(prediction)
    decision_text = json.dumps(trace.get("decision", ""), ensure_ascii=False).lower()
    reply = _reply(prediction)
    if "low_evidence" in decision_text or bool(trace.get("low_evidence")):
        return True
    if _predicted_route(prediction) == "out_of_scope" or _primary_intent(prediction) == "out_of_scope":
        return True
    return any(pattern in reply for pattern in CLARIFICATION_PATTERNS)


def _is_unsafe_response(case: BenchmarkCase, prediction: dict[str, Any]) -> bool:
    reply = _reply(prediction)
    return any(action and action in reply for action in case.unsafe_actions)


def _is_unsupported_claim(prediction: dict[str, Any]) -> bool:
    reply = _reply(prediction)
    return any(pattern in reply for pattern in UNSUPPORTED_PATTERNS)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return float(ordered[index])


def _ratio(values: list[int]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _prediction_pairs(
    group: str, name: str, warnings: list[str]
) -> list[tuple[BenchmarkCase, dict[str, Any]]]:
    path = FINAL_V2_DIR / group / f"{name}_predictions.jsonl"
    if not path.exists():
        warnings.append(f"missing predictions: {path}")
        return []
    rows = read_jsonl(path)
    pairs: list[tuple[BenchmarkCase, dict[str, Any]]] = []
    for index, prediction in enumerate(rows, start=1):
        case = _case(prediction, warnings, f"{path}:line {index}")
        if case is not None:
            pairs.append((case, prediction))
    if not pairs:
        warnings.append(f"no valid predictions loaded: {path}")
    return pairs


def _rc_from_pairs(pairs: list[tuple[BenchmarkCase, dict[str, Any]]]) -> float:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case, prediction in pairs:
        key = case.clean_id or case.canonical_id or case.clean_query or case.id
        grouped[str(key)].append(prediction)
    comparable = 0
    consistent = 0
    for predictions in grouped.values():
        if len(predictions) < 2:
            continue
        signature = (_predicted_route(predictions[0]), _protocol_id(predictions[0]))
        for prediction in predictions[1:]:
            comparable += 1
            if (_predicted_route(prediction), _protocol_id(prediction)) == signature:
                consistent += 1
    return float(consistent / comparable) if comparable else 0.0


def _metric_values(pairs: list[tuple[BenchmarkCase, dict[str, Any]]]) -> dict[str, Any]:
    route = [
        int(_predicted_route(prediction) == case.expected_route)
        for case, prediction in pairs
        if case.expected_route
    ]
    protocol = [
        int(_protocol_id(prediction) == case.expected_protocol_id)
        for case, prediction in pairs
        if case.expected_protocol_id
    ]
    primary = [
        int(_primary_intent(prediction) == case.expected_primary_intent)
        for case, prediction in pairs
        if case.expected_primary_intent
    ]
    high_risk = [
        int(_is_high_risk_prediction(prediction))
        for case, prediction in pairs
        if _is_high_risk_case(case)
    ]
    unsafe = [int(_is_unsafe_response(case, prediction)) for case, prediction in pairs]
    unsupported = [int(_is_unsupported_claim(prediction)) for _case, prediction in pairs]
    clarification = [
        int(_is_clarification_correct(case, prediction))
        for case, prediction in pairs
        if _is_low_evidence_case(case, prediction)
    ]
    latencies = [
        latency for _case, prediction in pairs if (latency := _latency(prediction)) is not None
    ]
    response_lengths = [len(_reply(prediction)) for _case, prediction in pairs]
    hrr = _ratio(high_risk)
    return {
        "num_cases": len(pairs),
        "RouteAcc": _ratio(route),
        "ProtocolAcc": _ratio(protocol),
        "PrimaryIntentAcc": _ratio(primary),
        "HRR": hrr,
        "HMR": 1.0 - hrr if high_risk else 0.0,
        "URR": _ratio(unsafe),
        "UCR": _ratio(unsupported),
        "RC": _rc_from_pairs(pairs),
        "ClarificationAcc": _ratio(clarification),
        "avg_latency_ms": float(mean(latencies)) if latencies else 0.0,
        "p95_latency_ms": _p95(latencies),
        "avg_response_length": float(mean(response_lengths)) if response_lengths else 0.0,
        "num_route_eval_cases": len(route),
        "num_protocol_eval_cases": len(protocol),
        "num_primary_intent_eval_cases": len(primary),
        "num_high_risk_cases": len(high_risk),
        "num_low_evidence_cases": len(clarification),
    }


def _metric_row_from_pairs(group: str, name: str, pairs: list[tuple[BenchmarkCase, dict[str, Any]]]) -> dict[str, Any]:
    values = _metric_values(pairs)
    return {"group": group, "name": name, **values}


def _write_warnings(warnings: list[str]) -> None:
    path = FINAL_V2_DIR / "statistics" / "statistics_warnings.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if warnings:
        lines = ["# final_v2 statistics warnings", ""]
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines = ["# final_v2 statistics warnings", "", "- None"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bootstrap_mean(values: list[int | float], rng: random.Random) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    estimates: list[float] = []
    n = len(values)
    for _ in range(BOOTSTRAP_N):
        sample_sum = 0.0
        for _idx in range(n):
            sample_sum += float(values[rng.randrange(n)])
        estimates.append(sample_sum / n)
    estimates.sort()
    lower_idx = int(0.025 * BOOTSTRAP_N)
    upper_idx = min(BOOTSTRAP_N - 1, int(0.975 * BOOTSTRAP_N))
    return float(sum(values) / n), estimates[lower_idx], estimates[upper_idx]


def _bootstrap_rc(pairs: list[tuple[BenchmarkCase, dict[str, Any]]], rng: random.Random) -> tuple[float, float, float]:
    grouped: dict[str, list[tuple[BenchmarkCase, dict[str, Any]]]] = defaultdict(list)
    for case, prediction in pairs:
        key = case.clean_id or case.canonical_id or case.clean_query or case.id
        grouped[str(key)].append((case, prediction))
    groups = [value for value in grouped.values() if len(value) >= 2]
    if not groups:
        return 0.0, 0.0, 0.0
    estimates = []
    for _ in range(BOOTSTRAP_N):
        sampled: list[tuple[BenchmarkCase, dict[str, Any]]] = []
        for _idx in range(len(groups)):
            sampled.extend(groups[rng.randrange(len(groups))])
        estimates.append(_rc_from_pairs(sampled))
    estimates.sort()
    return _rc_from_pairs(pairs), estimates[int(0.025 * BOOTSTRAP_N)], estimates[min(BOOTSTRAP_N - 1, int(0.975 * BOOTSTRAP_N))]


def _bootstrap_rows(all_pairs: dict[tuple[str, str], list[tuple[BenchmarkCase, dict[str, Any]]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rng = random.Random(BOOTSTRAP_SEED)
    for (group, name), pairs in sorted(all_pairs.items()):
        indicators = {
            "RouteAcc": [
                int(_predicted_route(prediction) == case.expected_route)
                for case, prediction in pairs
                if case.expected_route
            ],
            "HRR": [
                int(_is_high_risk_prediction(prediction))
                for case, prediction in pairs
                if _is_high_risk_case(case)
            ],
            "URR": [int(_is_unsafe_response(case, prediction)) for case, prediction in pairs],
            "UCR": [int(_is_unsupported_claim(prediction)) for _case, prediction in pairs],
        }
        for metric, values in indicators.items():
            mean_value, lower, upper = _bootstrap_mean(values, rng)
            rows.append(
                {
                    "group": group,
                    "name": name,
                    "metric": metric,
                    "mean": mean_value,
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "n": len(values),
                    "bootstrap_n": BOOTSTRAP_N,
                    "seed": BOOTSTRAP_SEED,
                }
            )
        mean_value, lower, upper = _bootstrap_rc(pairs, rng)
        rows.append(
            {
                "group": group,
                "name": name,
                "metric": "RC",
                "mean": mean_value,
                "ci_lower": lower,
                "ci_upper": upper,
                "n": len(pairs),
                "bootstrap_n": BOOTSTRAP_N,
                "seed": BOOTSTRAP_SEED,
            }
        )
    return rows


def _perturbation_rows(method_pairs: dict[str, list[tuple[BenchmarkCase, dict[str, Any]]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in MAIN_METHODS:
        grouped: dict[str, list[tuple[BenchmarkCase, dict[str, Any]]]] = defaultdict(list)
        for case, prediction in method_pairs.get(method, []):
            perturbation = str(_case_dict(prediction).get("perturbation_type") or case.perturbation_type or "")
            grouped[perturbation].append((case, prediction))
        for perturbation in ("filler_noise", "long_context", "repetition"):
            rows.append(
                {
                    "method": method,
                    "perturbation_type": perturbation,
                    **_metric_values(grouped.get(perturbation, [])),
                }
            )
    return rows


def _de_multiseed_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in DE_SEEDS:
        seed_dir = FINAL_V2_DIR / "de_multiseed" / f"seed_{seed}"
        metrics = read_json(seed_dir / "de_best_metrics.json")
        best_trial = metrics.get("best_trial")
        if not isinstance(best_trial, dict):
            best_trial = {}
        rows.append(
            {
                "seed": seed,
                "best_fitness": metrics.get("best_fitness", best_trial.get("fitness", "")),
                "policy_path": metrics.get(
                    "output_policy_path", str(seed_dir / f"policy_de_seed_{seed}.json")
                ),
                "trials_path": str(seed_dir / "de_trials.csv"),
                "curve_path": str(seed_dir / "de_curve.csv"),
                "best_metrics_path": str(seed_dir / "de_best_metrics.json"),
                "n_trials": len(read_csv_rows(seed_dir / "de_trials.csv")),
                "route_accuracy_clean": best_trial.get("route_accuracy_clean", ""),
                "route_accuracy_robust": best_trial.get("route_accuracy_robust", ""),
                "high_risk_recall": best_trial.get("high_risk_recall", ""),
                "unsafe_response_rate": best_trial.get("unsafe_response_rate", ""),
                "p95_latency_ms": best_trial.get("p95_latency_ms", ""),
            }
        )
    return rows


def _write_de_multiseed(rows: list[dict[str, Any]]) -> dict[str, str]:
    out_dir = FINAL_V2_DIR / "de_multiseed"
    csv_path = out_dir / "de_multiseed_summary.csv"
    md_path = out_dir / "de_multiseed_summary.md"
    fields = [
        "seed",
        "best_fitness",
        "n_trials",
        "route_accuracy_clean",
        "route_accuracy_robust",
        "high_risk_recall",
        "unsafe_response_rate",
        "p95_latency_ms",
        "policy_path",
        "trials_path",
        "curve_path",
        "best_metrics_path",
    ]
    write_csv(csv_path, rows, fields)
    write_markdown_table(md_path, rows, fields)
    return {"csv": str(csv_path), "markdown": str(md_path)}


def export_statistics_v2(only_de_multiseed: bool = False) -> dict[str, Any]:
    statistics_dir = FINAL_V2_DIR / "statistics"
    statistics_dir.mkdir(parents=True, exist_ok=True)
    de_rows = _de_multiseed_rows()
    de_outputs = _write_de_multiseed(de_rows)
    if only_de_multiseed:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "de_multiseed_rows": len(de_rows),
            "outputs": de_outputs,
        }

    warnings: list[str] = []
    all_pairs: dict[tuple[str, str], list[tuple[BenchmarkCase, dict[str, Any]]]] = {}
    final_rows: list[dict[str, Any]] = []
    robust_pairs_by_method: dict[str, list[tuple[BenchmarkCase, dict[str, Any]]]] = {}

    for method in MAIN_METHODS:
        clean_pairs = _prediction_pairs("clean", method, warnings)
        robust_pairs = _prediction_pairs("robust", method, warnings)
        all_pairs[("clean", method)] = clean_pairs
        all_pairs[("robust", method)] = robust_pairs
        robust_pairs_by_method[method] = robust_pairs
        final_rows.append(_metric_row_from_pairs("clean", method, clean_pairs))
        final_rows.append(_metric_row_from_pairs("robust", method, robust_pairs))

    ablation_rows: list[dict[str, Any]] = []
    for ablation in ABLATIONS:
        pairs = _prediction_pairs("ablation", ablation, warnings)
        all_pairs[("ablation", ablation)] = pairs
        ablation_rows.append(_metric_row_from_pairs("ablation", ablation, pairs))

    perturbation_rows = _perturbation_rows(robust_pairs_by_method)
    bootstrap_rows = _bootstrap_rows(all_pairs)

    metric_fields = ["group", "name", "num_cases", *METRIC_FIELDS, "num_route_eval_cases", "num_protocol_eval_cases", "num_primary_intent_eval_cases", "num_high_risk_cases", "num_low_evidence_cases"]
    write_csv(statistics_dir / "final_metrics_by_method.csv", final_rows, metric_fields)
    write_json(
        statistics_dir / "final_metrics_by_method.json",
        {"generated_at": datetime.now(UTC).isoformat(), "rows": final_rows},
    )
    write_csv(statistics_dir / "perturbation_metrics.csv", perturbation_rows, ["method", "perturbation_type", "num_cases", *METRIC_FIELDS])
    write_csv(statistics_dir / "ablation_metrics.csv", ablation_rows, metric_fields)
    write_csv(statistics_dir / "bootstrap_ci.csv", bootstrap_rows, ["group", "name", "metric", "mean", "ci_lower", "ci_upper", "n", "bootstrap_n", "seed"])
    write_markdown_table(statistics_dir / "bootstrap_ci.md", bootstrap_rows, ["group", "name", "metric", "mean", "ci_lower", "ci_upper", "n"])
    _write_warnings(warnings)

    data_counts = {
        filename: count_jsonl(DATA_V2_DIR / filename)
        for filename in (
            "clean_dev.jsonl",
            "robustness_dev.jsonl",
            "clean_test.jsonl",
            "robustness_test.jsonl",
        )
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_dir": str(FINAL_V2_DIR),
        "data_counts": data_counts,
        "warnings": warnings,
        "final_metrics_rows": len(final_rows),
        "perturbation_rows": len(perturbation_rows),
        "ablation_rows": len(ablation_rows),
        "bootstrap_rows": len(bootstrap_rows),
        "de_multiseed_rows": de_rows,
        "outputs": {
            "final_metrics_by_method_csv": str(statistics_dir / "final_metrics_by_method.csv"),
            "final_metrics_by_method_json": str(statistics_dir / "final_metrics_by_method.json"),
            "perturbation_metrics_csv": str(statistics_dir / "perturbation_metrics.csv"),
            "ablation_metrics_csv": str(statistics_dir / "ablation_metrics.csv"),
            "bootstrap_ci_csv": str(statistics_dir / "bootstrap_ci.csv"),
            "bootstrap_ci_md": str(statistics_dir / "bootstrap_ci.md"),
            "statistics_warnings_md": str(statistics_dir / "statistics_warnings.md"),
            "de_multiseed_summary_csv": de_outputs["csv"],
            "de_multiseed_summary_md": de_outputs["markdown"],
        },
    }
    write_json(statistics_dir / "final_v2_statistics.json", payload)
    return payload


def _metric_row(group: str, name: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "group": group,
        "name": name,
        "num_cases": summary.get("num_cases", ""),
        "route_accuracy": summary.get("route_accuracy", ""),
        "primary_intent_accuracy": summary.get("primary_intent_accuracy", ""),
        "high_risk_recall": summary.get("high_risk_recall", ""),
        "unsafe_response_rate": summary.get("unsafe_response_rate", ""),
        "unsupported_claim_rate": summary.get("unsupported_claim_rate", ""),
        "robust_consistency": summary.get("robust_consistency", ""),
        "p95_latency_ms": summary.get("p95_latency_ms", ""),
        "summary_path": summary.get("_source", ""),
    }


def _summaries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in MAIN_METHODS:
        summary = load_summary("clean", method)
        if summary:
            rows.append(_metric_row("clean", method, summary))
    for method in MAIN_METHODS:
        summary = load_summary("robust", method)
        if summary:
            rows.append(_metric_row("robust", method, summary))
    for ablation in ABLATIONS:
        summary = load_summary("ablation", ablation)
        if summary:
            rows.append(_metric_row("ablation", ablation, summary))
    return rows


def _de_multiseed_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in DE_SEEDS:
        seed_dir = FINAL_V2_DIR / "de_multiseed" / f"seed_{seed}"
        metrics = read_json(seed_dir / "de_best_metrics.json")
        best_trial = metrics.get("best_trial")
        if not isinstance(best_trial, dict):
            best_trial = {}
        rows.append(
            {
                "seed": seed,
                "best_fitness": metrics.get("best_fitness", best_trial.get("fitness", "")),
                "policy_path": metrics.get(
                    "output_policy_path", str(seed_dir / f"policy_de_seed_{seed}.json")
                ),
                "trials_path": str(seed_dir / "de_trials.csv"),
                "curve_path": str(seed_dir / "de_curve.csv"),
                "best_metrics_path": str(seed_dir / "de_best_metrics.json"),
                "n_trials": len(read_csv_rows(seed_dir / "de_trials.csv")),
                "route_accuracy_clean": best_trial.get("route_accuracy_clean", ""),
                "route_accuracy_robust": best_trial.get("route_accuracy_robust", ""),
                "high_risk_recall": best_trial.get("high_risk_recall", ""),
                "unsafe_response_rate": best_trial.get("unsafe_response_rate", ""),
                "p95_latency_ms": best_trial.get("p95_latency_ms", ""),
            }
        )
    return rows


def _write_de_multiseed(rows: list[dict[str, Any]]) -> dict[str, str]:
    out_dir = FINAL_V2_DIR / "de_multiseed"
    csv_path = out_dir / "de_multiseed_summary.csv"
    md_path = out_dir / "de_multiseed_summary.md"
    fields = [
        "seed",
        "best_fitness",
        "n_trials",
        "route_accuracy_clean",
        "route_accuracy_robust",
        "high_risk_recall",
        "unsafe_response_rate",
        "p95_latency_ms",
        "policy_path",
        "trials_path",
        "curve_path",
        "best_metrics_path",
    ]
    write_csv(csv_path, rows, fields)
    lines = [
        "# final_v2 DE multiseed summary",
        "",
        "| seed | best_fitness | n_trials | policy_path |",
        "|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('seed')} | {row.get('best_fitness')} | {row.get('n_trials')} | {row.get('policy_path')} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"csv": str(csv_path), "markdown": str(md_path)}


def export_statistics(only_de_multiseed: bool = False) -> dict[str, Any]:
    de_rows = _de_multiseed_rows()
    de_outputs = _write_de_multiseed(de_rows)
    if only_de_multiseed:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "de_multiseed_rows": len(de_rows),
            "outputs": de_outputs,
        }

    summary_rows = _summaries()
    statistics_dir = FINAL_V2_DIR / "statistics"
    statistics_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = statistics_dir / "summary_metrics.csv"
    write_csv(
        summary_csv,
        summary_rows,
        [
            "group",
            "name",
            "num_cases",
            "route_accuracy",
            "primary_intent_accuracy",
            "high_risk_recall",
            "unsafe_response_rate",
            "unsupported_claim_rate",
            "robust_consistency",
            "p95_latency_ms",
            "summary_path",
        ],
    )
    data_counts = {
        filename: count_jsonl(DATA_V2_DIR / filename)
        for filename in (
            "clean_dev.jsonl",
            "robustness_dev.jsonl",
            "clean_test.jsonl",
            "robustness_test.jsonl",
        )
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_dir": str(FINAL_V2_DIR),
        "data_counts": data_counts,
        "summary_rows": summary_rows,
        "de_multiseed_rows": de_rows,
        "outputs": {
            "summary_metrics_csv": str(summary_csv),
            "de_multiseed_summary_csv": de_outputs["csv"],
            "de_multiseed_summary_md": de_outputs["markdown"],
        },
    }
    write_json(statistics_dir / "final_v2_statistics.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export final_v2 statistics.")
    parser.add_argument("--only-de-multiseed", action="store_true")
    args = parser.parse_args(argv)
    result = export_statistics_v2(only_de_multiseed=args.only_de_multiseed)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
