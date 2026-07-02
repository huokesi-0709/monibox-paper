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
    parser.add_argument("--model")
    parser.add_argument("--setting")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    summary = evaluate_generation_outputs(
        input_paths=args.inputs,
        out_path=args.out,
        summary_path=args.summary,
        model=args.model,
        setting=args.setting,
        manifest_path=args.manifest,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def evaluate_generation_outputs(
    *,
    input_paths: list[Path],
    out_path: Path,
    summary_path: Path,
    model: str | None = None,
    setting: str | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    manifest_meta = _manifest_metadata(manifest_path)
    inferred_model = model or _str_or_none(manifest_meta.get("model"))
    inferred_setting = setting or _str_or_none(manifest_meta.get("setting"))
    rows: list[dict[str, Any]] = []
    for input_path in input_paths:
        rows.extend(
            _evaluate_file(
                input_path,
                model=inferred_model,
                setting=inferred_setting,
            )
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )

    metrics = _summarize(rows)
    runtime_meta = _runtime_metadata(rows)
    counts = _case_counts(rows)
    latency_summary = _latency_summary(rows)
    summary = {
        "inputs": [str(path) for path in input_paths],
        "output": str(out_path),
        "num_cases": len(rows),
        "manifest": str(manifest_path) if manifest_path else None,
        "metrics": metrics,
        "safe_metrics": metrics,
        "latency_summary": latency_summary,
        **runtime_meta,
        **metrics,
        **counts,
        "ParseOkRate": _parse_ok_rate(rows),
        "AvgLatencyMs": latency_summary.get("avg_ms"),
        "P95LatencyMs": latency_summary.get("p95_ms"),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _evaluate_file(
    input_path: Path, *, model: str | None, setting: str | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in input_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        payload = _with_generation_defaults(payload, model=model, setting=setting)
        if payload.get("status") == "failed":
            rows.append(
                {
                    **payload,
                    "evaluation": {
                        "skipped": True,
                        "reason": "generation status is failed",
                        "error": payload.get("error"),
                    },
                    "rubric": {},
                    "rubric_metrics": {},
                    "rubric_reasons": {},
                    "review_note": "Rubric was not run for failed generation outputs.",
                }
            )
            continue
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
    completed_rows = _completed_rows(rows)
    if not completed_rows:
        return _empty_summary()
    totals = dict.fromkeys(_metric_names(), 0.0)
    for row in completed_rows:
        metrics = _metric_dict(row)
        for name in totals:
            totals[name] += float(metrics.get(name, 0.0))
    count = len(completed_rows)
    summary = {name: totals[name] / count for name in totals}
    summary["NumCases"] = len(rows)
    return summary


def _empty_summary() -> dict[str, Any]:
    return dict.fromkeys(_metric_names(), 0.0) | {"NumCases": 0}


def _metric_dict(row: dict[str, Any]) -> dict[str, Any]:
    rubric = row.get("rubric")
    if isinstance(rubric, dict):
        metrics = rubric.get("metrics")
        if isinstance(metrics, dict):
            normalized = dict(metrics)
            if "SafeResponseRate" not in normalized and "SafeResponse" in normalized:
                normalized["SafeResponseRate"] = normalized["SafeResponse"]
            return normalized
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


def _with_generation_defaults(
    payload: dict[str, Any], *, model: str | None, setting: str | None
) -> dict[str, Any]:
    row = dict(payload)
    row["status"] = str(row.get("status") or "ok")
    if row.get("model") in (None, "") and model:
        row["model"] = model
    if row.get("setting") in (None, "") and setting:
        row["setting"] = setting
    if row.get("generator_model") in (None, "") and row.get("model"):
        row["generator_model"] = row.get("model")
    return row


def _completed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("status") != "failed"]


def _case_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    failed = sum(1 for row in rows if row.get("status") == "failed")
    completed = len(rows) - failed
    return {
        "NumCases": len(rows),
        "CompletedCases": completed,
        "FailedCases": failed,
    }


def _parse_ok_rate(rows: list[dict[str, Any]]) -> float | None:
    completed = _completed_rows(rows)
    if not completed:
        return None
    ok_count = 0
    for row in completed:
        parsed = row.get("parsed_output")
        trace = row.get("trace")
        parse_ok = None
        if isinstance(parsed, dict) and "_parse_ok" in parsed:
            parse_ok = bool(parsed.get("_parse_ok"))
        elif isinstance(trace, dict) and "parse_ok" in trace:
            parse_ok = bool(trace.get("parse_ok"))
        if parse_ok:
            ok_count += 1
    return ok_count / len(completed)


def _runtime_metadata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    metadata: dict[str, Any] = {}
    for key in (
        "model",
        "setting",
        "system",
        "generator",
        "generator_model",
        "generator_provider",
        "generator_base_url",
    ):
        value = _first_present(rows, key)
        if value not in (None, ""):
            metadata[key] = value
    if "model" in metadata:
        metadata["Model"] = metadata["model"]
    if "setting" in metadata:
        metadata["Setting"] = metadata["setting"]
    return metadata


def _first_present(rows: list[dict[str, Any]], key: str) -> Any:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    missing = 0
    for row in rows:
        value = row.get("latency_ms")
        if value is None:
            missing += 1
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            missing += 1
    if not values:
        return {
            "count": 0,
            "missing_count": missing,
            "note": "latency_ms was not recorded for these generation outputs.",
        }
    values.sort()
    count = len(values)
    avg = sum(values) / count
    return {
        "count": count,
        "missing_count": missing,
        "avg_ms": round(avg, 3),
        "p50_ms": round(values[int((count - 1) * 0.5)], 3),
        "p95_ms": round(values[int((count - 1) * 0.95)], 3),
        "max_ms": round(values[-1], 3),
    }


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _manifest_metadata(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    main()
