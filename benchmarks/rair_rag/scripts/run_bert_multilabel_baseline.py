from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_metrics import compute_routing_metrics
from benchmarks.rair_rag.routing_schema import load_routing_cases
from runtime.risk_router import RiskAwareInputRouter, route_for_intent

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "build" / "rair_eval" / "rair_test_bert-multilabel_predictions.jsonl"
DEFAULT_SUMMARY = PROJECT_ROOT / "build" / "rair_eval" / "rair_test_bert-multilabel_summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local BERT-MultiLabel baseline proxy.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    summary = run_bert_multilabel_baseline(args.data, args.out, args.summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_bert_multilabel_baseline(data_path: Path, out_path: Path, summary_path: Path) -> dict[str, Any]:
    cases = load_routing_cases(data_path)
    router = RiskAwareInputRouter()
    predictions: list[dict[str, Any]] = []
    for case in cases:
        mentions = router.extract_risk_mentions(case.canonical_input)
        positive = dedupe(str(item.get("risk") or "") for item in mentions if not item.get("negated"))
        primary = positive[0] if positive else "out_of_scope"
        predicted_route = route_for_intent(primary)
        prediction = {
            "id": case.id,
            "method": "bert-multilabel",
            "raw_input": case.raw_input,
            "canonical_input": case.canonical_input,
            "primary_intent": primary,
            "secondary_intents": positive[1:],
            "operational_constraints": ["low_battery"] if "low_battery" in positive else [],
            "positive_risks": positive,
            "negated_risks": [],
            "predicted_route": predicted_route or ("route_out_of_scope" if primary == "out_of_scope" else None),
            "protocol_id": None,
            "suppressed_protocols": [],
            "risk_score": 0.5 if primary != "out_of_scope" else 0.05,
            "risk_candidates": mentions,
            "risk_mentions": mentions,
            "risk_context": {
                "primary_intent": primary,
                "secondary_intents": positive[1:],
                "positive_risks": positive,
                "negated_risks": [],
                "operational_constraints": ["low_battery"] if "low_battery" in positive else [],
                "suppressed_protocols": [],
                "predicted_route": predicted_route or ("route_out_of_scope" if primary == "out_of_scope" else None),
                "protocol_id": None,
                "risk_score": 0.5 if primary != "out_of_scope" else 0.05,
                "risk_candidates": mentions,
            },
            "trace": {"baseline": "local proxy for BERT-MultiLabel"},
        }
        predictions.append(prediction)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in predictions) + "\n",
        encoding="utf-8",
    )
    summary = compute_routing_metrics(cases, predictions)
    payload = {
        "data": str(data_path),
        "method": "bert-multilabel",
        "num_cases": len(cases),
        "metrics": summary,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def dedupe(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "")
        if item and item not in output:
            output.append(item)
    return output


if __name__ == "__main__":
    main()
