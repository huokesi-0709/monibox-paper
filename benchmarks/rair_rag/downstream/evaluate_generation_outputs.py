from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.downstream.rubric import evaluate_generation
from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate downstream generation outputs with the RAIR rubric."
    )
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    summary = evaluate_generation_outputs(
        input_paths=args.inputs, out_path=args.out, summary_path=args.summary
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def evaluate_generation_outputs(
    *, input_paths: list[Path], out_path: Path, summary_path: Path
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for input_path in input_paths:
        rows.extend(_evaluate_file(input_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )

    metrics = _summarize(rows)
    summary = {
        "inputs": [str(path) for path in input_paths],
        "output": str(out_path),
        "num_cases": len(rows),
        "metrics": metrics,
        "safe_metrics": metrics,
        **metrics,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _evaluate_file(input_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        case_payload = _dict_value(payload.get("case")) or payload
        case = DownstreamCase.from_dict(case_payload)
        generation_output = _generation_output_from_payload(payload)
        evidence = [
            RetrievedEvidence(**item)
            if isinstance(item, dict)
            else RetrievedEvidence(**item.to_dict())
            for item in _list_value(payload.get("retrieved_evidence"))
        ]
        risk_context = _dict_value(payload.get("risk_context")) or _dict_value(
            case_payload.get("risk_context")
        )
        rubric = evaluate_generation(case, generation_output, evidence, risk_context)
        rows.append(
            {
                **payload,
                "evaluation": rubric,
                "rubric": rubric,
                "rubric_metrics": rubric.get("metrics", {}),
                "rubric_reasons": rubric.get("reasons", {}),
                "review_note": rubric.get("review_note", ""),
            }
        )
    return rows


def _generation_output_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    parsed_output = payload.get("parsed_output")
    if not isinstance(parsed_output, dict):
        parsed_output = {
            "protocol_id": payload.get("predicted_protocol_id"),
            "reply": payload.get("raw_output") or "",
            "safety_notes": [],
            "used_evidence": [],
            "_parse_ok": False,
        }
    return {
        "id": payload.get("id"),
        "system": payload.get("system"),
        "raw_input": payload.get("raw_input"),
        "prompt": payload.get("prompt", ""),
        "raw_output": payload.get("raw_output", ""),
        "parsed_output": parsed_output,
        "risk_context": _dict_value(payload.get("risk_context")),
        "retrieved_evidence": _list_value(payload.get("retrieved_evidence")),
        "predicted_protocol_id": payload.get("predicted_protocol_id"),
        "trace": _dict_value(payload.get("trace")),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _empty_summary()
    totals = dict.fromkeys(_metric_names(), 0.0)
    for row in rows:
        metrics = _metric_dict(row)
        for name in totals:
            totals[name] += float(metrics.get(name, 0.0))
    count = len(rows)
    summary = {name: totals[name] / count for name in totals}
    summary["NumCases"] = count
    return summary


def _empty_summary() -> dict[str, Any]:
    return dict.fromkeys(_metric_names(), 0.0) | {"NumCases": 0}


def _metric_dict(row: dict[str, Any]) -> dict[str, Any]:
    rubric = row.get("rubric")
    if isinstance(rubric, dict):
        metrics = rubric.get("metrics")
        if isinstance(metrics, dict):
            return metrics
    return {}


def _metric_names() -> list[str]:
    return [
        "SafeResponseRate",
        "CorrectProtocolUse",
        "NegatedRiskAvoidance",
        "HighRiskActionRecall",
        "ConstraintRetention",
        "EvidenceUseCorrectness",
        "BriefnessForVoice",
    ]


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    main()
