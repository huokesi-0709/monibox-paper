from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from experiments.final_v2_utils import DATA_V2_DIR, FINAL_V2_DIR, MAIN_METHODS, read_jsonl, write_json


CASE_TYPES = (
    "severe_bleeding",
    "respiratory_distress",
    "crush_trapped",
    "negation_conflict",
    "unsafe_request",
    "low_evidence",
    "multi_intent",
)
METHOD_LABELS = {
    "vanilla-rag": "Vanilla-RAG",
    "rag-guard": "RAG-Guard",
    "hsc-rag-manual": "HSC-RAG-manual",
    "hsc-rag-de": "HSC-RAG-DE",
}


def _case(prediction: dict[str, Any]) -> dict[str, Any]:
    case = prediction.get("case")
    return case if isinstance(case, dict) else {}


def _metadata_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for filename in (
        "clean_dev.jsonl",
        "robustness_dev.jsonl",
        "clean_test.jsonl",
        "robustness_test.jsonl",
    ):
        for row in read_jsonl(DATA_V2_DIR / filename):
            case_id = str(row.get("id") or "")
            if case_id:
                index[case_id] = row
    return index


def _trace(prediction: dict[str, Any]) -> dict[str, Any]:
    trace = prediction.get("trace")
    return trace if isinstance(trace, dict) else {}


def _method_from_path_name(path_name: str) -> str:
    for method in MAIN_METHODS:
        if path_name.startswith(method):
            return method
    return path_name.replace("_predictions.jsonl", "")


def _load_grouped_predictions() -> tuple[dict[str, dict[str, Any]], list[str]]:
    warnings: list[str] = []
    metadata = _metadata_index()
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"predictions": {}})
    for suite in ("clean", "robust"):
        suite_dir = FINAL_V2_DIR / suite
        for path in sorted(suite_dir.glob("*_predictions.jsonl")):
            method = _method_from_path_name(path.name)
            if method not in MAIN_METHODS:
                continue
            for prediction in read_jsonl(path):
                case = _case(prediction)
                case_id = str(prediction.get("case_id") or case.get("id") or "")
                if not case_id:
                    warnings.append(f"{path}: prediction missing case_id")
                    continue
                enriched_case = dict(case)
                if case_id in metadata:
                    enriched_case.update(metadata[case_id])
                item = grouped[case_id]
                item["case"] = item.get("case") or enriched_case
                item["suite"] = suite
                item["predictions"][method] = prediction
    if not grouped:
        warnings.append("no clean/robust predictions found under build/eval/final_v2")
    return dict(grouped), warnings


def _matches(case_type: str, case: dict[str, Any]) -> bool:
    scenario = str(case.get("scenario_family") or "")
    intent = str(case.get("expected_primary_intent") or "")
    evidence = str(case.get("evidence_level") or "")
    if case_type == "low_evidence":
        return evidence == "low" or scenario == "out_of_scope_low_evidence" or intent == "out_of_scope"
    if case_type == "multi_intent":
        return scenario == "multi_intent_priority"
    return scenario == case_type or intent == case_type


def _score(case_type: str, item: dict[str, Any]) -> tuple[int, int, str]:
    case = item.get("case") or {}
    suite_score = 1 if item.get("suite") == "robust" else 0
    risk_score = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(case.get("risk_level") or ""), 0)
    return suite_score, risk_score, str(case.get("id") or "")


def _trace_summary(prediction: dict[str, Any] | None) -> dict[str, Any]:
    if not prediction:
        return {}
    trace = _trace(prediction)
    intent_context = trace.get("intent_context")
    protocol_match = trace.get("protocol_match")
    return {
        "predicted_route": prediction.get("predicted_route") or trace.get("primary_intent"),
        "primary_intent": prediction.get("primary_intent") or trace.get("primary_intent"),
        "protocol_id": prediction.get("protocol_id") or trace.get("protocol_id"),
        "decision": trace.get("decision"),
        "guard_level": trace.get("guard_level"),
        "low_evidence": bool(trace.get("low_evidence")),
        "latency_ms": prediction.get("latency_ms") or trace.get("latency_ms"),
        "negated_risks": intent_context.get("negated_risks") if isinstance(intent_context, dict) else [],
        "negation_conflict": protocol_match.get("negation_conflict") if isinstance(protocol_match, dict) else False,
    }


def _case_payload(case_type: str, item: dict[str, Any]) -> dict[str, Any]:
    case = item.get("case") or {}
    predictions = item.get("predictions") or {}
    outputs: dict[str, Any] = {}
    for method in MAIN_METHODS:
        prediction = predictions.get(method)
        outputs[METHOD_LABELS[method]] = {
            "reply": "" if prediction is None else str(prediction.get("reply") or ""),
            "trace_summary": _trace_summary(prediction),
        }
    return {
        "case_type": case_type,
        "case_id": case.get("id"),
        "query": case.get("query"),
        "clean_query": case.get("clean_query"),
        "scenario_family": case.get("scenario_family"),
        "perturbation_type": case.get("perturbation_type"),
        "risk_level": case.get("risk_level"),
        "evidence_level": case.get("evidence_level"),
        "expected_route": case.get("expected_route"),
        "expected_protocol_id": case.get("expected_protocol_id"),
        "expected_primary_intent": case.get("expected_primary_intent"),
        "method_outputs": outputs,
        "final_interpretation_placeholder": "请基于上述真实输出撰写论文案例分析；不要加入没有被 prediction 或 trace 支撑的结论。",
    }


def _write_markdown(path: str, selected_cases: list[dict[str, Any]], warnings: list[str]) -> None:
    lines = ["# final_v2 selected test cases", ""]
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    for case in selected_cases:
        lines.append(f"## {case['case_type']} / {case.get('case_id')}")
        lines.append("")
        lines.append(f"- expected_route: `{case.get('expected_route')}`")
        lines.append(f"- expected_protocol_id: `{case.get('expected_protocol_id')}`")
        lines.append(f"- risk_level: `{case.get('risk_level')}`")
        lines.append(f"- perturbation_type: `{case.get('perturbation_type')}`")
        lines.append("")
        lines.append("```text")
        lines.append(str(case.get("query") or ""))
        lines.append("```")
        lines.append("")
        for method, output in (case.get("method_outputs") or {}).items():
            lines.append(f"### {method}")
            lines.append("")
            lines.append("```text")
            lines.append(str(output.get("reply") or ""))
            lines.append("```")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(output.get("trace_summary") or {}, ensure_ascii=False, indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
        lines.append(f"> {case['final_interpretation_placeholder']}")
        lines.append("")
    output = FINAL_V2_DIR / "cases" / path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def export_cases() -> dict[str, Any]:
    out_dir = FINAL_V2_DIR / "cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    grouped, warnings = _load_grouped_predictions()
    selected: list[dict[str, Any]] = []
    for case_type in CASE_TYPES:
        candidates = [item for item in grouped.values() if _matches(case_type, item.get("case") or {})]
        candidates.sort(key=lambda item: _score(case_type, item), reverse=True)
        if len(candidates) < 2:
            warnings.append(f"{case_type}: selected {len(candidates)} cases, expected at least 2")
        for item in candidates[:2]:
            selected.append(_case_payload(case_type, item))
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_types": list(CASE_TYPES),
        "selected_case_count": len(selected),
        "warnings": warnings,
        "selected_cases": selected,
    }
    write_json(out_dir / "selected_cases.json", payload)
    _write_markdown("selected_cases.md", selected, warnings)
    return {
        "selected_case_count": len(selected),
        "warnings": warnings,
        "outputs": {
            "json": str(out_dir / "selected_cases.json"),
            "markdown": str(out_dir / "selected_cases.md"),
        },
    }


def main() -> int:
    report = export_cases()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
