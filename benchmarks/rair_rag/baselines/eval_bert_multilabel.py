from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.baselines.bert_multilabel_dataset import LABELS
from benchmarks.rair_rag.baselines.bert_multilabel_predictor import (
    DEFAULT_BERT_MODEL_DIR,
    BertMultilabelPredictor,
)
from benchmarks.rair_rag.routing_metrics import compute_routing_metrics
from benchmarks.rair_rag.routing_schema import load_routing_cases
from benchmarks.rair_rag.run_routing_eval import prediction_from_context

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_OUT = PROJECT_ROOT / "build" / "bert_multilabel" / "test_predictions.jsonl"
DEFAULT_SUMMARY = PROJECT_ROOT / "build" / "bert_multilabel" / "test_summary.json"
DEFAULT_ROUTING_OUT = (
    PROJECT_ROOT / "build" / "rair_eval" / "rair_test_bert-multilabel_predictions.jsonl"
)
DEFAULT_ROUTING_SUMMARY = (
    PROJECT_ROOT / "build" / "rair_eval" / "rair_test_bert-multilabel_summary.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the trained bert-base-chinese multilabel baseline."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_BERT_MODEL_DIR)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument(
        "--routing-out",
        type=Path,
        default=DEFAULT_ROUTING_OUT,
        help="Optional compatibility copy for build/rair_eval routing tables.",
    )
    parser.add_argument(
        "--routing-summary",
        type=Path,
        default=DEFAULT_ROUTING_SUMMARY,
        help="Optional compatibility summary for build/rair_eval routing tables.",
    )
    args = parser.parse_args()
    summary = eval_bert_multilabel(
        data_path=args.data,
        model_dir=args.model_dir,
        threshold=args.threshold,
        out_path=args.out,
        summary_path=args.summary,
        routing_out_path=args.routing_out,
        routing_summary_path=args.routing_summary,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def eval_bert_multilabel(
    *,
    data_path: Path,
    model_dir: Path,
    threshold: float | None,
    out_path: Path,
    summary_path: Path,
    routing_out_path: Path | None = None,
    routing_summary_path: Path | None = None,
) -> dict[str, Any]:
    cases = load_routing_cases(data_path)
    predictor = BertMultilabelPredictor(model_dir=model_dir, threshold=threshold)
    predictions = [
        prediction_from_context(
            case=case,
            method="bert-multilabel",
            context=predictor.predict_case(case),
        )
        for case in cases
    ]
    metrics = compute_routing_metrics(cases, predictions)
    write_jsonl(out_path, predictions)
    summary = {
        "data": str(data_path),
        "method": "bert-multilabel",
        "model": "bert-base-chinese",
        "model_dir": str(model_dir),
        "label_space": list(LABELS),
        "threshold": predictor.threshold,
        "num_cases": len(cases),
        "metrics": metrics,
    }
    write_json(summary_path, summary)
    if routing_out_path and routing_out_path != out_path:
        write_jsonl(routing_out_path, predictions)
    if routing_summary_path and routing_summary_path != summary_path:
        write_json(routing_summary_path, summary)
    return summary


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
