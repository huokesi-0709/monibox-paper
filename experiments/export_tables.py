from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

MAIN_FIELDS = [
    "method",
    "route_accuracy",
    "evidence_hit_at_5",
    "high_risk_recall",
    "unsafe_response_rate",
    "unsupported_claim_rate",
    "avg_latency_ms",
    "p95_latency_ms",
    "num_cases",
    "num_predictions",
    "num_evidence_eval_cases",
    "num_high_risk_cases",
    "num_protocol_eval_cases",
]

ROBUSTNESS_FIELDS = [
    "method",
    "robust_route_accuracy",
    "primary_intent_accuracy",
    "protocol_false_trigger_rate",
    "robust_consistency",
    "unsafe_response_rate",
    "num_cases",
    "num_predictions",
    "num_evidence_eval_cases",
    "num_high_risk_cases",
    "num_protocol_eval_cases",
]

ABLATION_FIELDS = [
    "ablation",
    "disabled_modules",
    "route_accuracy",
    "robust_route_accuracy",
    "high_risk_recall",
    "unsafe_response_rate",
    "num_cases",
    "num_predictions",
    "num_high_risk_cases",
]

DE_EFFECT_FIELDS = [
    "policy",
    "fitness",
    "clean_route_accuracy",
    "robust_route_accuracy",
    "high_risk_miss_rate",
    "unsafe_response_rate",
]

LATENCY_FIELDS = [
    "method",
    "suite",
    "avg_latency_ms",
    "p95_latency_ms",
    "num_cases",
]

TRACE_AUDIT_FIELDS = [
    "method",
    "suite",
    "num_predictions",
    "num_with_trace",
    "num_low_evidence",
    "low_evidence_rate",
    "num_protocol_decisions",
    "avg_protocol_confidence",
    "num_guarded",
    "num_with_top_chunks",
    "num_with_score_breakdown",
]

TABLE_SPECS = {
    "main_results": MAIN_FIELDS,
    "robustness_results": ROBUSTNESS_FIELDS,
    "ablation_results": ABLATION_FIELDS,
    "de_effect_results": DE_EFFECT_FIELDS,
    "trace_audit_results": TRACE_AUDIT_FIELDS,
}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _summary_key(path: Path) -> str:
    name = path.name
    for suffix in ("_summary.json", "_summary.csv"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _load_summaries(eval_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    summaries: dict[str, dict[str, Any]] = {}

    json_paths = sorted(eval_dir.rglob("*_summary.json"))
    csv_paths = sorted(eval_dir.rglob("*_summary.csv"))

    for path in json_paths:
        try:
            row = _read_json(path)
        except Exception as exc:
            warnings.append(f"skip unreadable summary JSON {path}: {exc}")
            continue
        row["_source"] = str(path)
        summaries[_summary_key(path)] = row

    for path in csv_paths:
        key = _summary_key(path)
        if key in summaries:
            continue
        try:
            rows = _read_csv_rows(path)
        except Exception as exc:
            warnings.append(f"skip unreadable summary CSV {path}: {exc}")
            continue
        if not rows:
            warnings.append(f"skip empty summary CSV {path}")
            continue
        row = rows[0]
        row["_source"] = str(path)
        summaries[key] = row

    if not summaries:
        warnings.append(f"no *_summary.json or *_summary.csv found under {eval_dir}")
    return list(summaries.values()), warnings


def _is_robust(row: dict[str, Any]) -> bool:
    text = f"{row.get('data', '')} {row.get('_source', '')}".replace("\\", "/").lower()
    return "robust" in text or "robustness" in text


def _is_ablation(row: dict[str, Any]) -> bool:
    ablation = str(row.get("ablation") or "").strip()
    method = str(row.get("method") or "")
    return bool(ablation) or method.startswith("without_")


def _value(row: dict[str, Any], key: str, default: Any = "") -> Any:
    value = row.get(key, default)
    return default if value is None else value


def _metric(row: dict[str, Any], key: str, default: Any = "") -> Any:
    if key == "evidence_hit_at_5":
        return row.get("evidence_hit_at_5", row.get("evidence_hit_at_3", default))
    return row.get(key, default)


def _method(row: dict[str, Any]) -> str:
    return str(row.get("method") or row.get("ablation") or "unknown")


def _suite_from_path(path: Path) -> str:
    text = str(path).replace("\\", "/").lower()
    if "ablation" in text:
        return "ablation"
    if "robust" in text or "robustness" in text:
        return "robust"
    if "clean" in text:
        return "clean"
    return "unknown"


def _preferred_summary_key(row: dict[str, Any], suite: str) -> tuple[int, str]:
    source = str(row.get("_source") or "").replace("\\", "/").lower()
    official_rank = 0
    if f"/{suite}/" in source:
        official_rank = 2
    elif "/main/" in source and suite == "clean":
        official_rank = 1
    created_at = str(row.get("created_at") or "")
    return official_rank, created_at


def _dedupe_summaries_by_method(
    summaries: list[dict[str, Any]], suite: str
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in summaries:
        method = _method(row)
        current = grouped.get(method)
        if current is None or _preferred_summary_key(row, suite) > _preferred_summary_key(
            current, suite
        ):
            grouped[method] = row
    return list(grouped.values())


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    text = str(value)
    try:
        number = float(text)
    except ValueError:
        return text
    return f"{number:.6g}"


def build_main_results(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    candidates = [
        row for row in summaries if not _is_ablation(row) and not _is_robust(row)
    ]
    for row in _dedupe_summaries_by_method(candidates, "clean"):
        rows.append({field: _metric(row, field) for field in MAIN_FIELDS})
        rows[-1]["method"] = _method(row)
    return sorted(rows, key=lambda item: str(item["method"]))


def build_robustness_results(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        row for row in summaries if not _is_ablation(row) and _is_robust(row)
    ]
    rows = [
        {
            "method": _method(row),
            "robust_route_accuracy": _metric(row, "route_accuracy"),
            "primary_intent_accuracy": _metric(row, "primary_intent_accuracy"),
            "protocol_false_trigger_rate": _metric(row, "protocol_false_trigger_rate"),
            "robust_consistency": _metric(row, "robust_consistency"),
            "unsafe_response_rate": _metric(row, "unsafe_response_rate"),
            "num_cases": _metric(row, "num_cases"),
            "num_predictions": _metric(row, "num_predictions"),
            "num_evidence_eval_cases": _metric(row, "num_evidence_eval_cases"),
            "num_high_risk_cases": _metric(row, "num_high_risk_cases"),
            "num_protocol_eval_cases": _metric(row, "num_protocol_eval_cases"),
        }
        for row in _dedupe_summaries_by_method(candidates, "robust")
    ]
    return sorted(rows, key=lambda item: str(item["method"]))


def build_ablation_results(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in summaries:
        if not _is_ablation(row):
            continue
        name = str(row.get("ablation") or row.get("method") or "unknown")
        current = grouped.setdefault(
            name,
            {
                "ablation": name,
                "disabled_modules": _value(row, "disabled_modules"),
                "route_accuracy": "",
                "robust_route_accuracy": "",
                "high_risk_recall": "",
                "unsafe_response_rate": "",
                "num_cases": "",
                "num_predictions": "",
                "num_high_risk_cases": "",
            },
        )
        if _is_robust(row):
            current["robust_route_accuracy"] = _metric(row, "route_accuracy")
        else:
            current["route_accuracy"] = _metric(row, "route_accuracy")
        current["high_risk_recall"] = _metric(row, "high_risk_recall")
        current["unsafe_response_rate"] = _metric(row, "unsafe_response_rate")
        current["num_cases"] = _metric(row, "num_cases")
        current["num_predictions"] = _metric(row, "num_predictions")
        current["num_high_risk_cases"] = _metric(row, "num_high_risk_cases")
        if row.get("disabled_modules"):
            current["disabled_modules"] = row["disabled_modules"]
    return sorted(grouped.values(), key=lambda item: str(item["ablation"]))


def build_latency_memory_results(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in summaries:
        suite = "robust" if _is_robust(row) else "clean"
        if _is_ablation(row):
            suite = f"ablation_{suite}"
        rows.append(
            {
                "method": _method(row),
                "suite": suite,
                "avg_latency_ms": _metric(row, "avg_latency_ms"),
                "p95_latency_ms": _metric(row, "p95_latency_ms"),
                "num_cases": _metric(row, "num_cases"),
            }
        )
    return sorted(rows, key=lambda item: (str(item["method"]), str(item["suite"])))


def build_de_effect_results(eval_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    path = eval_dir / "de_best_metrics.json"
    if not path.exists():
        warnings.append(f"missing DE best metrics: {path}")
        return [], warnings
    try:
        obj = _read_json(path)
    except Exception as exc:
        warnings.append(f"skip unreadable DE best metrics {path}: {exc}")
        return [], warnings

    trial = obj.get("best_trial") if isinstance(obj.get("best_trial"), dict) else {}
    if not trial:
        warnings.append(f"DE best metrics has no best_trial: {path}")
        return [], warnings

    high_risk_miss_rate = trial.get("high_risk_miss_rate", "")
    if high_risk_miss_rate == "" and trial.get("high_risk_recall") not in (None, ""):
        high_risk_miss_rate = 1.0 - float(trial["high_risk_recall"])

    return [
        {
            "policy": obj.get("output_policy_path") or "scoring/policy_de.json",
            "fitness": trial.get("fitness", ""),
            "clean_route_accuracy": trial.get("route_accuracy_clean", ""),
            "robust_route_accuracy": trial.get("route_accuracy_robust", ""),
            "high_risk_miss_rate": high_risk_miss_rate,
            "unsafe_response_rate": trial.get("unsafe_response_rate", ""),
        }
    ], warnings


def _read_predictions(eval_dir: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    warnings: list[str] = []
    rows: list[tuple[Path, dict[str, Any]]] = []
    paths = sorted(eval_dir.rglob("*_predictions.jsonl"))
    if not paths:
        warnings.append(f"no *_predictions.jsonl found under {eval_dir}")
        return rows, warnings

    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            warnings.append(f"skip unreadable predictions JSONL {path}: {exc}")
            continue
        for lineno, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception as exc:
                warnings.append(f"skip invalid prediction {path}:line {lineno}: {exc}")
                continue
            if isinstance(obj, dict):
                rows.append((path, obj))
            else:
                warnings.append(f"skip non-object prediction {path}:line {lineno}")
    return rows, warnings


def _trace(prediction: dict[str, Any]) -> dict[str, Any]:
    trace = prediction.get("trace")
    return trace if isinstance(trace, dict) else {}


def _metadata(trace: dict[str, Any]) -> dict[str, Any]:
    metadata = trace.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _jsonish_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "")


def _is_low_evidence(trace: dict[str, Any]) -> bool:
    if bool(trace.get("low_evidence")):
        return True
    return "low_evidence" in _jsonish_text(trace.get("decision")).lower()


def _is_protocol_decision(prediction: dict[str, Any], trace: dict[str, Any]) -> bool:
    protocol_id = prediction.get("protocol_id") or trace.get("protocol_id")
    if protocol_id:
        return True
    return _jsonish_text(trace.get("decision")).lower().startswith("protocol")


def _is_guarded(trace: dict[str, Any]) -> bool:
    guard_level = str(trace.get("guard_level") or "").lower()
    guard_reasons = trace.get("guard_reasons") or []
    if guard_level and guard_level != "allow":
        return True
    if isinstance(guard_reasons, list) and guard_reasons:
        return True
    output_guard = trace.get("output_guard") or trace.get("guard_result")
    if isinstance(output_guard, dict):
        level = str(output_guard.get("level") or "").lower()
        reasons = output_guard.get("reasons") or []
        return (bool(level) and level != "allow") or bool(reasons)
    return False


def _top_chunks(trace: dict[str, Any]) -> list[Any]:
    chunks = trace.get("top_chunks")
    return chunks if isinstance(chunks, list) else []


def _protocol_confidence(trace: dict[str, Any]) -> float | None:
    value = trace.get("protocol_confidence")
    if value is None and isinstance(trace.get("protocol_match"), dict):
        value = trace["protocol_match"].get("confidence")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_trace_audit_results(eval_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    predictions, warnings = _read_predictions(eval_dir)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for path, prediction in predictions:
        trace = _trace(prediction)
        metadata = _metadata(trace)
        method = str(
            prediction.get("method") or metadata.get("method") or trace.get("method") or "unknown"
        )
        suite = str(metadata.get("suite") or trace.get("suite") or _suite_from_path(path))
        key = (method, suite)
        current = grouped.setdefault(
            key,
            {
                "method": method,
                "suite": suite,
                "num_predictions": 0,
                "num_with_trace": 0,
                "num_low_evidence": 0,
                "num_protocol_decisions": 0,
                "protocol_confidence_sum": 0.0,
                "protocol_confidence_count": 0,
                "num_guarded": 0,
                "num_with_top_chunks": 0,
                "num_with_score_breakdown": 0,
            },
        )
        current["num_predictions"] += 1
        if trace:
            current["num_with_trace"] += 1
        if _is_low_evidence(trace):
            current["num_low_evidence"] += 1
        if _is_protocol_decision(prediction, trace):
            current["num_protocol_decisions"] += 1
        confidence = _protocol_confidence(trace)
        if confidence is not None:
            current["protocol_confidence_sum"] += confidence
            current["protocol_confidence_count"] += 1
        if _is_guarded(trace):
            current["num_guarded"] += 1
        chunks = _top_chunks(trace)
        if chunks:
            current["num_with_top_chunks"] += 1
        if any(isinstance(chunk, dict) and chunk.get("score_breakdown") for chunk in chunks):
            current["num_with_score_breakdown"] += 1

    rows: list[dict[str, Any]] = []
    for current in grouped.values():
        num_predictions = int(current["num_predictions"])
        confidence_count = int(current["protocol_confidence_count"])
        rows.append(
            {
                "method": current["method"],
                "suite": current["suite"],
                "num_predictions": num_predictions,
                "num_with_trace": current["num_with_trace"],
                "num_low_evidence": current["num_low_evidence"],
                "low_evidence_rate": (
                    current["num_low_evidence"] / num_predictions
                    if num_predictions
                    else 0.0
                ),
                "num_protocol_decisions": current["num_protocol_decisions"],
                "avg_protocol_confidence": (
                    current["protocol_confidence_sum"] / confidence_count
                    if confidence_count
                    else 0.0
                ),
                "num_guarded": current["num_guarded"],
                "num_with_top_chunks": current["num_with_top_chunks"],
                "num_with_score_breakdown": current["num_with_score_breakdown"],
            }
        )
    return sorted(rows, key=lambda item: (str(item["method"]), str(item["suite"]))), warnings


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in fields})


def _write_markdown(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        cells = [_format_cell(row.get(field, "")).replace("|", "\\|") for field in fields]
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_tables(
    eval_dir: str | Path = "build/eval",
    out_dir: str | Path = "build/eval/tables",
) -> dict[str, Any]:
    eval_path = _resolve(eval_dir)
    out_path = _resolve(out_dir)
    summaries, warnings = _load_summaries(eval_path)

    tables = {
        "main_results": build_main_results(summaries),
        "robustness_results": build_robustness_results(summaries),
        "ablation_results": build_ablation_results(summaries),
        "latency_memory_results": build_latency_memory_results(summaries),
    }
    de_rows, de_warnings = build_de_effect_results(eval_path)
    warnings.extend(de_warnings)
    tables["de_effect_results"] = de_rows
    trace_rows, trace_warnings = build_trace_audit_results(eval_path)
    warnings.extend(trace_warnings)
    tables["trace_audit_results"] = trace_rows

    outputs: dict[str, str] = {}
    for name, rows in tables.items():
        fields = TABLE_SPECS.get(name, LATENCY_FIELDS)
        csv_path = eval_path / f"{name}.csv"
        _write_csv(csv_path, rows, fields)
        outputs[f"{name}_csv"] = str(csv_path)
        if name in TABLE_SPECS:
            md_path = out_path / f"{name}.md"
            _write_markdown(md_path, rows, fields)
            outputs[f"{name}_md"] = str(md_path)
        if not rows:
            warnings.append(f"no rows generated for {name}")

    return {
        "eval_dir": str(eval_path),
        "out_dir": str(out_path),
        "counts": {name: len(rows) for name, rows in tables.items()},
        "outputs": outputs,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export paper tables from build/eval summaries."
    )
    parser.add_argument("--eval-dir", default="build/eval")
    parser.add_argument("--out-dir", default="build/eval/tables")
    args = parser.parse_args()

    result = export_tables(args.eval_dir, args.out_dir)
    for warning in result["warnings"]:
        print(f"[export_tables][WARN] {warning}")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
