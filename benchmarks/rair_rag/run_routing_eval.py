from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_metrics import compute_routing_metrics
from benchmarks.rair_rag.routing_schema import RoutingCase, load_routing_cases
from benchmarks.rair_rag.scripts.generate_candidates import PROTOCOL_BY_ROUTE
from runtime.multi_intent_router import MultiIntentRouter
from runtime.negation_resolver import NegationConfig, NegationResolver
from runtime.risk_router import RiskAwareInputRouter
from runtime.routing_policy import RoutingPolicy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = PROJECT_ROOT / "build" / "rair_eval" / "predictions.jsonl"
DEFAULT_SUMMARY = PROJECT_ROOT / "build" / "rair_eval" / "summary.json"

SUPPORTED_METHODS = (
    "keyword-baseline",
    "no-negation",
    "single-intent",
    "risk-router",
    "risk-router-de",
)

ROUTE_BY_INTENT = {
    "respiratory_distress": "route_respiratory_distress",
    "severe_bleeding_or_shock": "route_bleeding_control",
    "trauma_or_fracture": "route_trauma_or_fracture",
    "crush_injury": "route_crush_injury",
    "altered_consciousness_or_head_injury": "route_head_or_consciousness",
    "hypothermia": "route_hypothermia",
    "psychological_distress": "route_psychological_support",
    "trapped_or_entrapment": "route_trapped_or_entrapment",
    "aftershock_or_collapse_hazard": "route_aftershock_or_collapse_hazard",
    "dehydration_or_resource_deprivation": "route_dehydration_or_resource_deprivation",
    "out_of_scope": "route_out_of_scope",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAIR-RAG routing evaluation without LLM or remote APIs."
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--method", choices=SUPPORTED_METHODS, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    summary = run_routing_eval(
        data_path=args.data,
        method=args.method,
        policy_path=args.policy,
        out_path=args.out,
        summary_path=args.summary,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_routing_eval(
    *,
    data_path: Path,
    method: str,
    policy_path: Path | None,
    out_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    summary = evaluate_routing_cases(
        data_path=data_path,
        method=method,
        policy_path=policy_path,
    )
    write_jsonl(out_path, summary["predictions"])
    summary_for_file = {key: value for key, value in summary.items() if key != "predictions"}
    write_json(summary_path, summary_for_file)
    return summary_for_file


def evaluate_routing_cases(
    *, data_path: Path, method: str, policy_path: Path | None
) -> dict[str, Any]:
    if method not in SUPPORTED_METHODS:
        allowed = ", ".join(SUPPORTED_METHODS)
        raise ValueError(f"unsupported method {method}; choose one of {allowed}")

    cases = load_routing_cases(data_path)
    policy = load_policy_for_method(method, policy_path)
    predictions = [
        predict_case(case=case, method=method, policy=policy) for case in cases
    ]
    metrics = compute_routing_metrics(cases, predictions)
    return {
        "data": str(data_path),
        "method": method,
        "policy": str(policy_path) if policy_path else None,
        "num_cases": len(cases),
        "metrics": metrics,
        "predictions": predictions,
    }


def load_policy_for_method(
    method: str, policy_path: Path | None
) -> RoutingPolicy | None:
    if method not in {"risk-router", "risk-router-de"}:
        return None
    if policy_path:
        return RoutingPolicy.from_file(policy_path)
    return RoutingPolicy()


def predict_case(
    *, case: RoutingCase, method: str, policy: RoutingPolicy | None
) -> dict[str, Any]:
    if method == "keyword-baseline":
        context = predict_keyword_baseline(case)
    elif method == "no-negation":
        context = predict_no_negation(case)
    elif method == "single-intent":
        context = predict_single_intent(case)
    elif method in {"risk-router", "risk-router-de"}:
        context = RiskAwareInputRouter(policy).route(
            case.raw_input, case.canonical_input
        )
    else:
        raise ValueError(f"unsupported method {method}")
    return prediction_from_context(case=case, method=method, context=context)


def predict_keyword_baseline(case: RoutingCase) -> dict[str, Any]:
    router = RiskAwareInputRouter()
    mentions = router.extract_risk_mentions(case.canonical_input)
    first = mentions[0] if mentions else {}
    primary = str(first.get("risk") or "out_of_scope")
    return {
        "primary_intent": primary,
        "secondary_intents": [],
        "operational_constraints": ["low_battery"] if primary == "low_battery" else [],
        "positive_risks": [] if primary == "out_of_scope" else [primary],
        "negated_risks": [],
        "risk_mentions": mentions,
        "risk_score": float(first.get("confidence") or 0.05),
        "trace": {"baseline": "first textual keyword match"},
    }


def predict_no_negation(case: RoutingCase) -> dict[str, Any]:
    router = RiskAwareInputRouter()
    mentions = router.extract_risk_mentions(case.canonical_input)
    route_result = MultiIntentRouter().route(mentions)
    return {
        "primary_intent": route_result.primary_intent,
        "secondary_intents": route_result.secondary_intents,
        "operational_constraints": route_result.operational_constraints,
        "positive_risks": dedupe(
            str(mention.get("risk") or "") for mention in mentions
        ),
        "negated_risks": [],
        "risk_mentions": mentions,
        "risk_score": route_result.risk_score,
        "trace": {
            "baseline": "all keyword matches treated as positive",
            "priority_trace": route_result.priority_trace,
        },
    }


def predict_single_intent(case: RoutingCase) -> dict[str, Any]:
    router = RiskAwareInputRouter()
    mentions = router.extract_risk_mentions(case.canonical_input)
    negation = NegationResolver(NegationConfig()).resolve(
        case.canonical_input, mentions
    )
    positive = [mention for mention in negation.mentions if not mention.get("negated")]
    best = max(
        positive,
        key=lambda mention: (
            float(mention.get("confidence") or 0.0),
            -int(mention.get("start") or 0),
        ),
        default={},
    )
    primary = str(best.get("risk") or "out_of_scope")
    operational = ["low_battery"] if primary == "low_battery" else []
    return {
        "primary_intent": primary,
        "secondary_intents": [],
        "operational_constraints": operational,
        "positive_risks": [] if primary == "out_of_scope" else [primary],
        "negated_risks": negation.negated_risks,
        "risk_mentions": negation.mentions,
        "risk_score": float(best.get("confidence") or 0.05),
        "trace": {
            "baseline": "highest-confidence positive keyword only",
            "negation_trace": negation.negation_trace,
        },
    }


def prediction_from_context(
    *, case: RoutingCase, method: str, context: Any
) -> dict[str, Any]:
    context_data = context.to_dict() if hasattr(context, "to_dict") else dict(context)
    primary_intent = str(context_data.get("primary_intent") or "out_of_scope")
    route = route_for_intent(primary_intent)
    protocol_id = PROTOCOL_BY_ROUTE.get(route)
    trace = context_data.get("trace")
    if not isinstance(trace, dict):
        trace = {}
    trace.update(
        {
            "route_name": route,
            "protocol_id": protocol_id,
            "primary_intent": primary_intent,
        }
    )
    return {
        "id": case.id,
        "method": method,
        "raw_input": case.raw_input,
        "canonical_input": case.canonical_input,
        "primary_intent": primary_intent,
        "secondary_intents": list(context_data.get("secondary_intents") or []),
        "operational_constraints": list(
            context_data.get("operational_constraints") or []
        ),
        "positive_risks": list(context_data.get("positive_risks") or []),
        "negated_risks": list(context_data.get("negated_risks") or []),
        "predicted_route": route,
        "protocol_id": protocol_id,
        "risk_score": float(context_data.get("risk_score") or 0.0),
        "risk_mentions": list(context_data.get("risk_mentions") or []),
        "trace": trace,
    }


def route_for_intent(intent: str) -> str:
    return ROUTE_BY_INTENT.get(intent, "")


def dedupe(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "")
        if item and item not in output:
            output.append(item)
    return output


def write_jsonl(path: Path, predictions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(prediction, ensure_ascii=False, sort_keys=True)
        for prediction in predictions
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
