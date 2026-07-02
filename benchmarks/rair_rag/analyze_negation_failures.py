from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_schema import RoutingCase, load_routing_cases

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "build" / "rair_eval" / "rair_test_risk-router_predictions.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "build" / "rair_eval" / "error_analysis" / "negation_failures.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze RAIR negation failures.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = analyze_negation_failures(
        data_path=args.data,
        predictions_path=args.predictions,
        out_path=args.out,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def analyze_negation_failures(
    *, data_path: Path, predictions_path: Path, out_path: Path, limit: int = 20
) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("--limit must be positive")
    cases = load_routing_cases(data_path)
    predictions = _load_predictions(predictions_path)
    by_id = {str(row.get("id")): row for row in predictions}
    failures = []
    for case in cases:
        prediction = by_id.get(case.id)
        if not prediction:
            continue
        gold = set(case.negated_risks)
        pred = _set_from_prediction(prediction, "negated_risks")
        if gold == pred:
            continue
        failures.append(
            {
                "case": case,
                "prediction": prediction,
                "gold": sorted(gold),
                "pred": sorted(pred),
                "missing": sorted(gold - pred),
                "extra": sorted(pred - gold),
                **classify_failure(case=case, prediction=prediction, gold=gold, pred=pred),
            }
        )
    selected = failures[:limit]
    write_markdown(out_path, selected, total_failures=len(failures), limit=limit)
    return {
        "data": str(data_path),
        "predictions": str(predictions_path),
        "out": str(out_path),
        "total_failures": len(failures),
        "reported_failures": len(selected),
    }


def classify_failure(
    *,
    case: RoutingCase,
    prediction: dict[str, Any],
    gold: set[str],
    pred: set[str],
) -> dict[str, str]:
    missing = gold - pred
    extra = pred - gold
    candidates = _risk_candidates(prediction)
    if missing and not any(str(item.get("risk")) in missing for item in candidates):
        return {
            "error_type": "missing_negated_candidate",
            "reason": "Gold negated risk was not present among predicted risk candidates.",
        }
    if missing and any(
        str(item.get("risk")) in missing and not bool(item.get("negated"))
        for item in candidates
    ):
        return {
            "error_type": "negation_scope_missed",
            "reason": "Gold negated risk was detected as a candidate but not marked negated.",
        }
    if extra:
        return {
            "error_type": "over_negation",
            "reason": "Prediction marked an additional risk as negated beyond gold labels.",
        }
    if case.should_not_trigger and not prediction.get("suppressed_protocols"):
        return {
            "error_type": "suppression_missing",
            "reason": "Gold has should_not_trigger protocols but prediction did not suppress any protocol.",
        }
    return {
        "error_type": "set_mismatch",
        "reason": "Gold and predicted negated_risks differ; no more specific rule matched.",
    }


def write_markdown(
    path: Path, failures: list[dict[str, Any]], *, total_failures: int, limit: int
) -> None:
    lines = [
        "# Negation Failure Cases",
        "",
        f"- Total mismatches: {total_failures}",
        f"- Reported: {len(failures)} of max {limit}",
        "",
        "This is preliminary rule-based error typing, not manual qualitative analysis.",
        "",
        "| ID | Gold Negated Risks | Predicted Negated Risks | Missing | Extra | Error Type | Reason | Raw Input |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in failures:
        case = item["case"]
        lines.append(
            "| {id} | {gold} | {pred} | {missing} | {extra} | {error_type} | {reason} | {raw_input} |".format(
                id=_escape(case.id),
                gold=_escape(", ".join(item["gold"])),
                pred=_escape(", ".join(item["pred"])),
                missing=_escape(", ".join(item["missing"])),
                extra=_escape(", ".join(item["extra"])),
                error_type=_escape(item["error_type"]),
                reason=_escape(item["reason"]),
                raw_input=_escape(case.raw_input),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_predictions(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _set_from_prediction(prediction: dict[str, Any], field_name: str) -> set[str]:
    value = prediction.get(field_name)
    if value is None and isinstance(prediction.get("risk_context"), dict):
        value = prediction["risk_context"].get(field_name)
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if item}


def _risk_candidates(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    value = prediction.get("risk_candidates")
    if value is None and isinstance(prediction.get("risk_context"), dict):
        value = prediction["risk_context"].get("risk_candidates")
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
