from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_metrics import compute_routing_metrics
from benchmarks.rair_rag.routing_schema import load_routing_cases
from benchmarks.rair_rag.run_routing_eval import (
    predict_candidate_multilabel,
    prediction_from_context,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "build" / "rair_eval" / "rair_test_candidate-multilabel_predictions.jsonl"
DEFAULT_SUMMARY = PROJECT_ROOT / "build" / "rair_eval" / "rair_test_candidate-multilabel_summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the candidate-multilabel routing proxy baseline."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    summary = run_candidate_multilabel_baseline(args.data, args.out, args.summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_candidate_multilabel_baseline(
    data_path: Path, out_path: Path, summary_path: Path
) -> dict[str, Any]:
    cases = load_routing_cases(data_path)
    predictions = [
        prediction_from_context(
            case=case,
            method="candidate-multilabel",
            context=predict_candidate_multilabel(case),
        )
        for case in cases
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in predictions)
        + "\n",
        encoding="utf-8",
    )
    payload = {
        "data": str(data_path),
        "method": "candidate-multilabel",
        "num_cases": len(cases),
        "metrics": compute_routing_metrics(cases, predictions),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    main()
