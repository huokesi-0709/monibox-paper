from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


MAIN_METHODS = ("vanilla-rag", "rag-guard", "hsc-rag-manual", "hsc-rag-de")
MAIN_METHOD_DISPLAY = {
    "vanilla-rag": "Vanilla-RAG",
    "rag-guard": "RAG-Guard",
    "hsc-rag-manual": "HSC-RAG-manual",
    "hsc-rag-de": "HSC-RAG-DE",
}
EXTRA_METHOD_DISPLAY = {
    "without_negation": "without_negation",
}

CASE_SPECS = (
    {
        "key": "case_1_severe_bleeding_robust",
        "title": "案例 1：严重出血 robust 输入",
        "coverage": "严重出血 robust 输入",
    },
    {
        "key": "case_2_trapped_or_crush_robust",
        "title": "案例 2：挤压受困 robust 输入",
        "coverage": "挤压受困 robust 输入",
    },
    {
        "key": "case_3_boundary_low_evidence",
        "title": "案例 3：模糊边界/低证据输入",
        "coverage": "模糊边界/低证据输入",
    },
    {
        "key": "case_4_negation_conflict",
        "title": "案例 4：否定冲突输入",
        "coverage": "否定冲突输入",
        "extra_methods": ("without_negation",),
    },
    {
        "key": "case_5_unsafe_request",
        "title": "案例 5：危险诱导请求",
        "coverage": "危险诱导请求",
    },
)

UNSAFE_QUERY_KEYWORDS = (
    "止血带",
    "药物剂量",
    "注射",
    "越具体越好",
    "直接告诉",
    "用药",
    "剂量",
    "ҩ�����",
    "ֹѪ��",
)


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _normalize_method(value: Any) -> str:
    text = str(value or "").strip()
    aliases = {
        "vanilla_rag": "vanilla-rag",
        "rag_guard": "rag-guard",
        "hsc_rag_manual": "hsc-rag-manual",
        "hsc_rag_de": "hsc-rag-de",
    }
    return aliases.get(text, text)


def _method_from_path(path: Path) -> str:
    stem = path.name.replace("_predictions.jsonl", "")
    for method in (*MAIN_METHODS, "without_negation"):
        if stem == method or method in stem:
            return method
    return _normalize_method(stem)


def _trace(prediction: dict[str, Any] | None) -> dict[str, Any]:
    if not prediction:
        return {}
    trace = prediction.get("trace")
    return trace if isinstance(trace, dict) else {}


def _case(prediction: dict[str, Any] | None) -> dict[str, Any]:
    if not prediction:
        return {}
    case = prediction.get("case")
    return case if isinstance(case, dict) else {}


def _method_label(method: str) -> str:
    return MAIN_METHOD_DISPLAY.get(method) or EXTRA_METHOD_DISPLAY.get(method) or method


def _load_predictions(eval_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    warnings: list[str] = []
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"predictions": {}})
    paths = sorted(eval_dir.rglob("*_predictions.jsonl"))
    if not paths:
        warnings.append(f"未找到 *_predictions.jsonl：{eval_dir}")
        return {}, warnings

    for path in paths:
        method_from_file = _method_from_path(path)
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    prediction = json.loads(line)
                except json.JSONDecodeError as exc:
                    warnings.append(f"跳过非法 JSONL：{path}:line {lineno}；原因：{exc}")
                    continue
                if not isinstance(prediction, dict):
                    warnings.append(f"跳过非对象 prediction：{path}:line {lineno}")
                    continue
                case_id = str(prediction.get("case_id") or _case(prediction).get("id") or "")
                if not case_id:
                    warnings.append(f"跳过缺少 case_id 的 prediction：{path}:line {lineno}")
                    continue
                method = _normalize_method(prediction.get("method")) or method_from_file
                method = method_from_file if method_from_file.startswith("without_") else method
                item = grouped[case_id]
                if not item.get("case"):
                    item["case"] = _case(prediction)
                item["predictions"][method] = prediction
    return dict(grouped), warnings


def _has_all_main_methods(group: dict[str, Any]) -> bool:
    predictions = group.get("predictions") or {}
    return all(method in predictions for method in MAIN_METHODS)


def _is_robust_case(case: dict[str, Any]) -> bool:
    return str(case.get("perturbation_type") or "") != "clean"


def _intent(case: dict[str, Any]) -> str:
    return str(case.get("expected_primary_intent") or case.get("expected_route") or "")


def _hsc_de_prediction(group: dict[str, Any]) -> dict[str, Any] | None:
    return (group.get("predictions") or {}).get("hsc-rag-de")


def _is_low_evidence(prediction: dict[str, Any] | None) -> bool:
    trace = _trace(prediction)
    decision = str(trace.get("decision") or "").lower()
    return bool(trace.get("low_evidence")) or "low_evidence" in decision


def _negation_signals(prediction: dict[str, Any] | None) -> dict[str, Any]:
    trace = _trace(prediction)
    intent_context = trace.get("intent_context")
    if not isinstance(intent_context, dict):
        intent_context = {}
    protocol_match = trace.get("protocol_match")
    if not isinstance(protocol_match, dict):
        protocol_match = {}
    return {
        "negated_risks": intent_context.get("negated_risks") or [],
        "negation_conflict": bool(protocol_match.get("negation_conflict")),
    }


def _is_negation_case(group: dict[str, Any]) -> bool:
    case = group.get("case") or {}
    signals = _negation_signals(_hsc_de_prediction(group))
    return bool(signals["negated_risks"] or signals["negation_conflict"] or _textual_negation_signal(case))


def _textual_negation_signal(case: dict[str, Any]) -> bool:
    query = str(case.get("query") or "")
    tags = " ".join(str(item) for item in (case.get("expected_tags") or []))
    return any(token in query or token in tags for token in ("没有", "没", "否定"))


def _unsafe_query_hits(case: dict[str, Any]) -> list[str]:
    query = str(case.get("query") or "")
    hits: list[str] = []
    for action in case.get("unsafe_actions") or []:
        action_text = str(action or "")
        if action_text and action_text in query:
            hits.append(action_text)
    for keyword in UNSAFE_QUERY_KEYWORDS:
        if keyword and keyword in query and keyword not in hits:
            hits.append(keyword)
    return hits


def _score_group(group: dict[str, Any]) -> tuple[int, int, str]:
    case = group.get("case") or {}
    perturbation = str(case.get("perturbation_type") or "")
    risk = str(case.get("risk_level") or "")
    preferred_perturbation = {"filler_noise": 3, "long_context": 2, "repetition": 1}.get(
        perturbation, 0
    )
    risk_score = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(risk, 0)
    return preferred_perturbation, risk_score, str(case.get("id") or "")


def _score_for_case_key(key: str, group: dict[str, Any]) -> tuple[Any, ...]:
    case = group.get("case") or {}
    signals = _negation_signals(_hsc_de_prediction(group))
    base = _score_group(group)
    if key == "case_2_trapped_or_crush_robust":
        no_negation = not (signals["negated_risks"] or signals["negation_conflict"])
        return (int(no_negation), *base)
    if key == "case_3_boundary_low_evidence":
        out_of_scope = _intent(case) == "out_of_scope"
        return (int(out_of_scope), *_score_group(group))
    if key == "case_4_negation_conflict":
        trace_negation = bool(signals["negated_risks"] or signals["negation_conflict"])
        conflict = bool(signals["negation_conflict"])
        return (int(trace_negation), int(conflict), *base)
    return base


def _pick_case(groups: dict[str, dict[str, Any]], key: str, warnings: list[str]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for group in groups.values():
        if not _has_all_main_methods(group):
            continue
        case = group.get("case") or {}
        hsc_de = _hsc_de_prediction(group)
        intent = _intent(case)
        if key == "case_1_severe_bleeding_robust":
            if _is_robust_case(case) and intent == "severe_bleeding" and not _is_negation_case(group):
                candidates.append(group)
        elif key == "case_2_trapped_or_crush_robust":
            if _is_robust_case(case) and intent == "trapped_or_crush":
                candidates.append(group)
        elif key == "case_3_boundary_low_evidence":
            unsafe_hits = _unsafe_query_hits(case)
            if _is_robust_case(case) and not unsafe_hits and (
                _is_low_evidence(hsc_de) or intent == "out_of_scope"
            ):
                candidates.append(group)
        elif key == "case_4_negation_conflict":
            predictions = group.get("predictions") or {}
            if _is_robust_case(case) and "without_negation" in predictions and _is_negation_case(group):
                candidates.append(group)
        elif key == "case_5_unsafe_request":
            if _is_robust_case(case) and _unsafe_query_hits(case):
                candidates.append(group)

    if not candidates:
        warnings.append(f"未找到候选案例：{key}")
        return None

    candidates.sort(key=lambda item: _score_for_case_key(key, item), reverse=True)
    return candidates[0]


def _trace_fields(prediction: dict[str, Any] | None) -> dict[str, Any]:
    if not prediction:
        return {}
    trace = _trace(prediction)
    intent_context = trace.get("intent_context")
    if not isinstance(intent_context, dict):
        intent_context = {}
    protocol_match = trace.get("protocol_match")
    if not isinstance(protocol_match, dict):
        protocol_match = {}
    return {
        "predicted_route": prediction.get("predicted_route") or trace.get("primary_intent"),
        "primary_intent": prediction.get("primary_intent") or trace.get("primary_intent"),
        "protocol_id": prediction.get("protocol_id") or trace.get("protocol_id"),
        "decision": trace.get("decision"),
        "guard_level": trace.get("guard_level"),
        "guard_reasons": trace.get("guard_reasons") or [],
        "low_evidence": trace.get("low_evidence"),
        "negated_risks": intent_context.get("negated_risks") or [],
        "negation_conflict": bool(protocol_match.get("negation_conflict")),
        "protocol_confidence": trace.get("protocol_confidence"),
        "latency_ms": prediction.get("latency_ms") or trace.get("latency_ms"),
    }


def _summary_for_method(prediction: dict[str, Any] | None) -> str:
    if not prediction:
        return "该方法没有找到对应 prediction。"
    fields = _trace_fields(prediction)
    reply = str(prediction.get("reply") or "")
    first = (
        f"预测 route 为 {fields.get('predicted_route') or '空'}，"
        f"协议为 {fields.get('protocol_id') or '空'}。"
    )
    second = (
        f"决策为 {fields.get('decision') or '空'}，"
        f"guard_level 为 {fields.get('guard_level') or '空'}，"
        f"low_evidence 为 {fields.get('low_evidence')}。"
    )
    third = f"回复长度 {len(reply)} 个字符，延迟 {fields.get('latency_ms')} ms。"
    return " ".join([first, second, third])


def _case_payload(spec: dict[str, Any], group: dict[str, Any]) -> dict[str, Any]:
    case = group.get("case") or {}
    predictions = group.get("predictions") or {}
    methods = list(MAIN_METHODS) + list(spec.get("extra_methods") or ())
    outputs: dict[str, Any] = {}
    for method in methods:
        prediction = predictions.get(method)
        outputs[_method_label(method)] = {
            "method_key": method,
            "reply": "" if prediction is None else str(prediction.get("reply") or ""),
            "summary": _summary_for_method(prediction),
            "selected_trace_fields": _trace_fields(prediction),
        }

    return {
        "case_type": spec["key"],
        "title": spec["title"],
        "coverage": spec["coverage"],
        "case_id": case.get("id") or group.get("case_id"),
        "query": case.get("query"),
        "clean_query": case.get("clean_query"),
        "perturbation_type": case.get("perturbation_type"),
        "expected_route": case.get("expected_route"),
        "expected_protocol_id": case.get("expected_protocol_id"),
        "risk_level": case.get("risk_level"),
        "expected_primary_intent": case.get("expected_primary_intent"),
        "expected_tags": case.get("expected_tags") or [],
        "unsafe_actions": case.get("unsafe_actions") or [],
        "unsafe_query_hits": _unsafe_query_hits(case),
        "selection_signals": {
            "low_evidence": _is_low_evidence(_hsc_de_prediction(group)),
            "textual_negation_signal": _textual_negation_signal(case),
            **_negation_signals(_hsc_de_prediction(group)),
        },
        "outputs": outputs,
        "safety_observation_placeholder": "待论文分析：请基于以上真实输出补充安全性观察，不要在此处写入未由输出支持的结论。",
    }


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|")


def _metadata_table(case: dict[str, Any]) -> str:
    rows = [
        ("case_id", case.get("case_id")),
        ("perturbation_type", case.get("perturbation_type")),
        ("expected_route", case.get("expected_route")),
        ("expected_protocol_id", case.get("expected_protocol_id")),
        ("risk_level", case.get("risk_level")),
        ("unsafe_query_hits", ", ".join(case.get("unsafe_query_hits") or [])),
    ]
    lines = ["| 字段 | 值 |", "| --- | --- |"]
    for key, value in rows:
        lines.append(f"| {key} | {_escape_md(value)} |")
    return "\n".join(lines)


def _write_markdown(path: Path, selected_cases: list[dict[str, Any]], warnings: list[str]) -> None:
    lines: list[str] = [
        "# 论文 4.5.2 典型案例真实输出",
        "",
        "> 本文件仅汇总 test predictions 中的真实输出和 trace 摘要；安全性解读保留为待论文分析。",
        "",
    ]
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    for case in selected_cases:
        lines.append(f"## {case['title']}")
        lines.append("")
        lines.append(_metadata_table(case))
        lines.append("")
        lines.append("**用户输入**")
        lines.append("")
        lines.append("```text")
        lines.append(str(case.get("query") or ""))
        lines.append("```")
        lines.append("")
        lines.append("**clean_query**")
        lines.append("")
        lines.append("```text")
        lines.append(str(case.get("clean_query") or ""))
        lines.append("```")
        lines.append("")
        lines.append(f"**unsafe_actions**：{', '.join(str(x) for x in case.get('unsafe_actions') or [])}")
        lines.append("")
        lines.append("**selected trace fields**")
        lines.append("")
        lines.append("```json")
        lines.append(
            json.dumps(case.get("selection_signals") or {}, ensure_ascii=False, indent=2, sort_keys=True)
        )
        lines.append("```")
        lines.append("")

        for method_label, output in case.get("outputs", {}).items():
            lines.append(f"### {method_label}")
            lines.append("")
            lines.append(f"摘要：{output.get('summary')}")
            lines.append("")
            lines.append("真实输出：")
            lines.append("")
            lines.append("```text")
            lines.append(str(output.get("reply") or ""))
            lines.append("```")
            lines.append("")
            lines.append("trace 摘要：")
            lines.append("")
            lines.append("```json")
            lines.append(
                json.dumps(
                    output.get("selected_trace_fields") or {},
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            lines.append("```")
            lines.append("")

        lines.append(f"**安全性观察占位**：{case['safety_observation_placeholder']}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def export_selected_cases(
    eval_dir: str | Path = "build/eval/test",
    out_dir: str | Path = "build/eval/test/cases",
) -> dict[str, Any]:
    eval_path = _resolve(eval_dir)
    out_path = _resolve(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    groups, warnings = _load_predictions(eval_path)

    selected_cases: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for spec in CASE_SPECS:
        group = _pick_case(groups, spec["key"], warnings)
        if not group:
            continue
        case_id = str((group.get("case") or {}).get("id") or "")
        if case_id in selected_ids:
            warnings.append(f"{spec['key']} 与前序案例选择到同一 case_id：{case_id}")
        selected_ids.add(case_id)
        selected_cases.append(_case_payload(spec, group))

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_dir": str(eval_path),
        "out_dir": str(out_path),
        "warnings": warnings,
        "selected_case_count": len(selected_cases),
        "selected_cases": selected_cases,
    }
    json_path = out_path / "selected_case_outputs.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path = out_path / "selected_case_outputs.md"
    _write_markdown(md_path, selected_cases, warnings)
    return {
        "eval_dir": str(eval_path),
        "out_dir": str(out_path),
        "selected_case_count": len(selected_cases),
        "selected_case_ids": [case.get("case_id") for case in selected_cases],
        "outputs": {
            "json": str(json_path),
            "markdown": str(md_path),
        },
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export selected real test prediction cases for paper section 4.5.2.")
    parser.add_argument("--eval-dir", default="build/eval/test")
    parser.add_argument("--out-dir", default="build/eval/test/cases")
    args = parser.parse_args(argv)

    report = export_selected_cases(args.eval_dir, args.out_dir)
    for warning in report["warnings"]:
        print(f"[export_selected_cases][WARN] {warning}")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
