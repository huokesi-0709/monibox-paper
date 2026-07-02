from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.run_routing_eval import evaluate_routing_cases
from runtime.routing_policy import RoutingPolicy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_POLICY = PROJECT_ROOT / "scoring" / "routing_policy_manual.yaml"
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "rair_eval" / "sensitivity"
NEGATION_PENALTY_VALUES = (0.0, 0.2, 0.45, 0.8, 2.0, 10.0)
HIGH_RISK_BOOST_VALUES = (0.0, 0.05, 0.1, 1.0, 10.0)
FIELDS = (
    "Parameter",
    "Value",
    "NumCases",
    "NegRiskF1",
    "PFTR",
    "HRR",
    "RouteAcc",
    "primary_intent_changed_count",
    "negated_risks_changed_count",
    "suppressed_protocols_changed_count",
    "avg_risk_score_delta",
    "avg_negation_probability_delta",
    "Warning",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAIR routing parameter connectivity diagnostics."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = run_sensitivity_eval(
        data_path=args.data,
        policy_path=args.policy,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def run_sensitivity_eval(
    *, data_path: Path, policy_path: Path | None, out_dir: Path
) -> dict[str, Any]:
    base_policy = RoutingPolicy.from_file(policy_path) if policy_path else RoutingPolicy()
    baseline = _evaluate_with_policy(data_path=data_path, policy=base_policy)
    rows = []
    warnings: list[str] = []
    negation_signatures: set[tuple[Any, ...]] = set()
    for value in NEGATION_PENALTY_VALUES:
        policy = replace(base_policy, negation_penalty=value)
        result = _evaluate_with_policy(data_path=data_path, policy=policy)
        diagnostics = _diagnostics(baseline, result)
        negation_signatures.add(_prediction_signature(result))
        rows.append(_row("negation_penalty", value, result, diagnostics))
    if len(negation_signatures) <= 1:
        warnings.append(
            "negation_penalty: parameter may not be connected to decision path."
        )

    boost_signatures: set[tuple[Any, ...]] = set()
    for value in HIGH_RISK_BOOST_VALUES:
        policy = replace(base_policy, high_risk_boost=value)
        result = _evaluate_with_policy(data_path=data_path, policy=policy)
        diagnostics = _diagnostics(baseline, result)
        boost_signatures.add(_prediction_signature(result))
        rows.append(_row("high_risk_boost", value, result, diagnostics))
    if len(boost_signatures) <= 1:
        warnings.append(
            "high_risk_boost: parameter may not be connected to decision path."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "routing_sensitivity.md"
    csv_path = out_dir / "routing_sensitivity.csv"
    write_markdown(md_path, rows, warnings=warnings)
    write_csv(csv_path, rows)
    return {
        "data": str(data_path),
        "policy": str(policy_path) if policy_path else "default RoutingPolicy",
        "num_rows": len(rows),
        "warnings": warnings,
        "outputs": {"markdown": str(md_path), "csv": str(csv_path)},
    }


def _evaluate_with_policy(*, data_path: Path, policy: RoutingPolicy) -> dict[str, Any]:
    return evaluate_routing_cases(
        data_path=data_path,
        method="risk-router",
        policy_path=None,
        policy=policy,
    )


def _row(
    parameter: str,
    value: float,
    result: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, str]:
    metrics = _metrics(result)
    return {
        "Parameter": parameter,
        "Value": _format_float(value),
        "NumCases": str(int(metrics.get("num_cases") or 0)),
        "NegRiskF1": _format_float(metrics.get("NegRiskF1")),
        "PFTR": _format_float(metrics.get("PFTR")),
        "HRR": _format_float(metrics.get("HRR")),
        "RouteAcc": _format_float(metrics.get("RouteAcc")),
        "primary_intent_changed_count": str(
            int(diagnostics.get("primary_intent_changed_count") or 0)
        ),
        "negated_risks_changed_count": str(
            int(diagnostics.get("negated_risks_changed_count") or 0)
        ),
        "suppressed_protocols_changed_count": str(
            int(diagnostics.get("suppressed_protocols_changed_count") or 0)
        ),
        "avg_risk_score_delta": _format_float(
            diagnostics.get("avg_risk_score_delta")
        ),
        "avg_negation_probability_delta": _format_float(
            diagnostics.get("avg_negation_probability_delta")
        ),
        "Warning": str(diagnostics.get("warning") or ""),
    }


def write_markdown(
    path: Path, rows: list[dict[str, str]], *, warnings: list[str] | None = None
) -> None:
    lines = [
        "# RAIR Routing Parameter Connectivity Diagnosis",
        "",
        "This diagnostic varies routing-policy parameters, including extreme values, to test whether each parameter is connected to the decision path. It should not be interpreted as parameter stability evidence.",
        "",
        "For `negation_penalty`, read `NegRiskF1`, `PFTR`, `negated_risks_changed_count`, `suppressed_protocols_changed_count`, and `avg_negation_probability_delta`.",
        "",
        "For `high_risk_boost`, read `HRR`, `RouteAcc`, `primary_intent_changed_count`, and `avg_risk_score_delta`.",
        "",
        "If all predictions remain identical across all tested values for a parameter, the report emits `parameter may not be connected to decision path`.",
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.extend(
        [
            "| Parameter | Value | NumCases | NegRiskF1 | PFTR | HRR | RouteAcc | primary_intent_changed_count | negated_risks_changed_count | suppressed_protocols_changed_count | avg_risk_score_delta | avg_negation_probability_delta | Warning |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    lines.extend(
        "| {Parameter} | {Value} | {NumCases} | {NegRiskF1} | {PFTR} | {HRR} | "
        "{RouteAcc} | {primary_intent_changed_count} | "
        "{negated_risks_changed_count} | {suppressed_protocols_changed_count} | "
        "{avg_risk_score_delta} | {avg_negation_probability_delta} | {Warning} |".format(
            **row
        )
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics")
    return metrics if isinstance(metrics, dict) else result


def _predictions(result: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = result.get("predictions")
    if isinstance(predictions, list):
        return [item for item in predictions if isinstance(item, dict)]
    return []


def _diagnostics(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    base_predictions = _predictions(baseline)
    current_predictions = _predictions(current)
    pairs = list(zip(base_predictions, current_predictions, strict=False))
    if not pairs:
        return {
            "primary_intent_changed_count": 0,
            "negated_risks_changed_count": 0,
            "suppressed_protocols_changed_count": 0,
            "avg_risk_score_delta": 0.0,
            "avg_negation_probability_delta": 0.0,
            "warning": "prediction diagnostics unavailable",
        }
    risk_score_deltas = []
    negation_probability_deltas = []
    primary_changes = 0
    negated_changes = 0
    suppressed_changes = 0
    for base, current_row in pairs:
        if base.get("primary_intent") != current_row.get("primary_intent"):
            primary_changes += 1
        if _sorted_tuple(base.get("negated_risks")) != _sorted_tuple(
            current_row.get("negated_risks")
        ):
            negated_changes += 1
        if _sorted_tuple(base.get("suppressed_protocols")) != _sorted_tuple(
            current_row.get("suppressed_protocols")
        ):
            suppressed_changes += 1
        risk_score_deltas.append(
            abs(_float_value(current_row.get("risk_score")) - _float_value(base.get("risk_score")))
        )
        negation_probability_deltas.append(
            abs(
                _avg_negation_probability(current_row)
                - _avg_negation_probability(base)
            )
        )
    return {
        "primary_intent_changed_count": primary_changes,
        "negated_risks_changed_count": negated_changes,
        "suppressed_protocols_changed_count": suppressed_changes,
        "avg_risk_score_delta": _mean(risk_score_deltas),
        "avg_negation_probability_delta": _mean(negation_probability_deltas),
        "warning": "",
    }


def _prediction_signature(result: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        (
            item.get("id"),
            item.get("primary_intent"),
            item.get("predicted_route"),
            item.get("protocol_id"),
            _sorted_tuple(item.get("negated_risks")),
            _sorted_tuple(item.get("suppressed_protocols")),
            round(_float_value(item.get("risk_score")), 6),
        )
        for item in _predictions(result)
    )


def _avg_negation_probability(prediction: dict[str, Any]) -> float:
    trace = prediction.get("trace")
    if not isinstance(trace, dict):
        return 0.0
    negation_trace = trace.get("negation_trace")
    if not isinstance(negation_trace, list):
        return 0.0
    values = [
        _float_value(item.get("negation_probability"))
        for item in negation_trace
        if isinstance(item, dict) and item.get("negation_probability") is not None
    ]
    return _mean(values)


def _sorted_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted(str(item) for item in value))


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _format_float(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


if __name__ == "__main__":
    main()
