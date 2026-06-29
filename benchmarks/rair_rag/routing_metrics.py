from __future__ import annotations

from collections import defaultdict
from typing import Any

from benchmarks.rair_rag.routing_schema import RoutingCase

HIGH_RISK_LEVELS = {"high", "critical"}
HIGH_RISK_INTENTS = {
    "respiratory_distress",
    "severe_bleeding_or_shock",
    "crush_injury",
    "altered_consciousness_or_head_injury",
    "aftershock_or_collapse_hazard",
    "trapped_or_entrapment",
}


def compute_routing_metrics(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    _ensure_same_length(cases, predictions)
    overall = _compute_group(cases, predictions)
    by_perturbation: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[tuple[RoutingCase, dict[str, Any]]]] = defaultdict(list)
    for case, prediction in zip(cases, predictions, strict=True):
        keys = case.perturbation_types or ["<none>"]
        for key in keys:
            groups[key].append((case, prediction))
    for key, pairs in sorted(groups.items()):
        grouped_cases = [case for case, _prediction in pairs]
        grouped_predictions = [prediction for _case, prediction in pairs]
        by_perturbation[key] = _compute_group(grouped_cases, grouped_predictions)
    return {**overall, "by_perturbation_type": by_perturbation}


def _compute_group(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "num_cases": len(cases),
        "RouteAcc": route_accuracy(cases, predictions),
        "HRR": high_risk_recall(cases, predictions),
        "PFTR": protocol_false_trigger_rate(cases, predictions),
        "NegRiskExact": negated_risk_exact(cases, predictions),
        "NegRiskF1": negated_risk_f1(cases, predictions),
        "PrimaryIntentAcc": primary_intent_accuracy(cases, predictions),
        "SecondaryIntentF1": secondary_intent_f1(cases, predictions),
        "ConstraintF1": constraint_f1(cases, predictions),
    }


def route_accuracy(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    return _ratio(
        sum(
            1
            for case, prediction in zip(cases, predictions, strict=True)
            if _predicted_route(prediction) == case.expected_route
        ),
        len(cases),
    )


def high_risk_recall(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    pairs = [
        (case, prediction)
        for case, prediction in zip(cases, predictions, strict=True)
        if _is_high_risk_case(case)
    ]
    hits = 0
    for case, prediction in pairs:
        primary = _primary_intent(prediction)
        if primary == case.primary_intent or primary in set(case.positive_risks) & HIGH_RISK_INTENTS:
            hits += 1
    return _ratio(hits, len(pairs))


def protocol_false_trigger_rate(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    false_triggers = 0
    for case, prediction in zip(cases, predictions, strict=True):
        protocol_id = _protocol_id(prediction)
        primary = _primary_intent(prediction)
        if (protocol_id and protocol_id in set(case.should_not_trigger)) or (primary and primary in set(case.negated_risks)):
            false_triggers += 1
    return _ratio(false_triggers, len(cases))


def negated_risk_exact(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    return _set_exact(cases, predictions, "negated_risks")


def negated_risk_f1(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    return _micro_set_f1(cases, predictions, "negated_risks")


def primary_intent_accuracy(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    return _ratio(
        sum(
            1
            for case, prediction in zip(cases, predictions, strict=True)
            if _primary_intent(prediction) == case.primary_intent
        ),
        len(cases),
    )


def secondary_intent_f1(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    return _micro_set_f1(cases, predictions, "secondary_intents")


def constraint_f1(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> float:
    return _micro_set_f1(cases, predictions, "operational_constraints")


def _ensure_same_length(
    cases: list[RoutingCase], predictions: list[dict[str, Any]]
) -> None:
    if len(cases) != len(predictions):
        raise ValueError(
            "cases/predictions length mismatch: "
            f"{len(cases)} cases vs {len(predictions)} predictions"
        )


def _predicted_route(prediction: dict[str, Any]) -> str | None:
    trace = _trace(prediction)
    return prediction.get("predicted_route") or trace.get("route_name")


def _protocol_id(prediction: dict[str, Any]) -> str | None:
    trace = _trace(prediction)
    return prediction.get("protocol_id") or trace.get("protocol_id")


def _primary_intent(prediction: dict[str, Any]) -> str | None:
    trace = _trace(prediction)
    return prediction.get("primary_intent") or trace.get("primary_intent")


def _trace(prediction: dict[str, Any]) -> dict[str, Any]:
    trace = prediction.get("trace")
    return trace if isinstance(trace, dict) else {}


def _predicted_set(prediction: dict[str, Any], field_name: str) -> set[str]:
    trace = _trace(prediction)
    value = prediction.get(field_name, trace.get(field_name, []))
    if value is None:
        return set()
    if not isinstance(value, list):
        raise ValueError(f"prediction {field_name} must be a list")
    return {str(item) for item in value}


def _gold_set(case: RoutingCase, field_name: str) -> set[str]:
    value = getattr(case, field_name)
    return {str(item) for item in value}


def _set_exact(
    cases: list[RoutingCase], predictions: list[dict[str, Any]], field_name: str
) -> float:
    return _ratio(
        sum(
            1
            for case, prediction in zip(cases, predictions, strict=True)
            if _gold_set(case, field_name) == _predicted_set(prediction, field_name)
        ),
        len(cases),
    )


def _micro_set_f1(
    cases: list[RoutingCase], predictions: list[dict[str, Any]], field_name: str
) -> float:
    tp = fp = fn = 0
    for case, prediction in zip(cases, predictions, strict=True):
        gold = _gold_set(case, field_name)
        pred = _predicted_set(prediction, field_name)
        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return _ratio(2 * precision * recall, precision + recall)


def _is_high_risk_case(case: RoutingCase) -> bool:
    return case.risk_level in HIGH_RISK_LEVELS or bool(
        set(case.positive_risks) & HIGH_RISK_INTENTS
    )


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0
