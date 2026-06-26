from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


DEFAULT_TARGET_SIZE = 100
CATEGORY_ORDER = (
    "high_or_critical",
    "robust",
    "negation_conflict",
    "unsafe_request",
    "low_evidence_or_boundary",
    "multi_intent",
)
CATEGORY_TARGETS = {
    "high_or_critical": 20,
    "robust": 25,
    "negation_conflict": 15,
    "unsafe_request": 15,
    "low_evidence_or_boundary": 15,
    "multi_intent": 10,
}
UNSAFE_QUERY_KEYWORDS = (
    "止血带",
    "药物剂量",
    "注射",
    "强行移动",
    "保证获救",
    "越具体越好",
    "ҩ�����",
    "ֹѪ��",
    "��֤���",
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
    return _normalize_method(stem)


def _trace(prediction: dict[str, Any]) -> dict[str, Any]:
    trace = prediction.get("trace")
    return trace if isinstance(trace, dict) else {}


def _case(prediction: dict[str, Any]) -> dict[str, Any]:
    case = prediction.get("case")
    return case if isinstance(case, dict) else {}


def _intent_context(trace: dict[str, Any]) -> dict[str, Any]:
    value = trace.get("intent_context")
    return value if isinstance(value, dict) else {}


def _protocol_match(trace: dict[str, Any]) -> dict[str, Any]:
    value = trace.get("protocol_match")
    return value if isinstance(value, dict) else {}


def _unsafe_hits(case: dict[str, Any]) -> list[str]:
    query = str(case.get("query") or "")
    hits: list[str] = []
    for action in case.get("unsafe_actions") or []:
        text = str(action or "")
        if text and text in query:
            hits.append(text)
    for keyword in UNSAFE_QUERY_KEYWORDS:
        if keyword and keyword in query and keyword not in hits:
            hits.append(keyword)
    return hits


def _trace_summary(prediction: dict[str, Any]) -> dict[str, Any]:
    trace = _trace(prediction)
    intent_context = _intent_context(trace)
    protocol_match = _protocol_match(trace)
    secondary = (
        prediction.get("secondary_intents")
        or trace.get("secondary_intents")
        or intent_context.get("secondary_intents")
        or []
    )
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
        "secondary_intents": secondary if isinstance(secondary, list) else [],
        "protocol_confidence": trace.get("protocol_confidence"),
        "latency_ms": prediction.get("latency_ms") or trace.get("latency_ms"),
    }


def _categories(prediction: dict[str, Any]) -> list[str]:
    case = _case(prediction)
    trace_summary = _trace_summary(prediction)
    categories: list[str] = []
    risk_level = str(case.get("risk_level") or "").lower()
    perturbation_type = str(case.get("perturbation_type") or "")
    expected_route = str(case.get("expected_route") or "")
    expected_intent = str(case.get("expected_primary_intent") or "")
    query = str(case.get("query") or "")
    tags = " ".join(str(item) for item in case.get("expected_tags") or [])

    if risk_level in {"high", "critical"}:
        categories.append("high_or_critical")
    if perturbation_type and perturbation_type != "clean":
        categories.append("robust")
    if (
        trace_summary["negated_risks"]
        or trace_summary["negation_conflict"]
        or any(token in query or token in tags for token in ("没有", "没", "否定"))
    ):
        categories.append("negation_conflict")
    if _unsafe_hits(case):
        categories.append("unsafe_request")
    if (
        trace_summary["low_evidence"]
        or "low_evidence" in str(trace_summary["decision"] or "").lower()
        or expected_route == "out_of_scope"
        or expected_intent == "out_of_scope"
    ):
        categories.append("low_evidence_or_boundary")
    if trace_summary["secondary_intents"]:
        categories.append("multi_intent")
    return categories


def _load_predictions(eval_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    paths = sorted(eval_dir.rglob("*_predictions.jsonl"))
    if not paths:
        msg = (
            f"未在 {eval_dir} 下找到 test predictions。"
            "请先运行 clean/robust/ablation test eval，不要用 dev 结果替代。"
        )
        raise FileNotFoundError(msg)

    rows: list[dict[str, Any]] = []
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
                case = _case(prediction)
                case_id = str(prediction.get("case_id") or case.get("id") or "")
                if not case_id:
                    warnings.append(f"跳过缺少 case_id 的 prediction：{path}:line {lineno}")
                    continue
                method = _normalize_method(prediction.get("method")) or method_from_file
                if method_from_file.startswith("without_"):
                    method = method_from_file
                item = {
                    "case_id": case_id,
                    "method": method,
                    "query": case.get("query") or prediction.get("query") or "",
                    "clean_query": case.get("clean_query") or "",
                    "perturbation_type": case.get("perturbation_type") or "",
                    "expected_route": case.get("expected_route") or "",
                    "expected_protocol_id": case.get("expected_protocol_id") or "",
                    "expected_primary_intent": case.get("expected_primary_intent") or "",
                    "risk_level": case.get("risk_level") or "",
                    "unsafe_actions": case.get("unsafe_actions") or [],
                    "system_reply": prediction.get("reply") or "",
                    "trace_summary": _trace_summary(prediction),
                    "source_path": str(path),
                    "source_line": lineno,
                    "unsafe_query_hits": _unsafe_hits(case),
                }
                item["coverage_tags"] = _categories(prediction)
                rows.append(item)
    if not rows:
        msg = (
            f"{eval_dir} 下存在 prediction 文件，但没有可导出的样本。"
            "请检查 test eval 输出是否为空。"
        )
        raise RuntimeError(msg)
    return rows, warnings


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    risk_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
        str(row.get("risk_level") or "").lower(), 4
    )
    perturb_rank = {"filler_noise": 0, "long_context": 1, "repetition": 2, "clean": 3}.get(
        str(row.get("perturbation_type") or ""), 4
    )
    return (
        str(row.get("method") or ""),
        risk_rank,
        perturb_rank,
        str(row.get("case_id") or ""),
    )


def _select_review_rows(rows: list[dict[str, Any]], target_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()
    category_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=_sort_key):
        for category in row.get("coverage_tags") or []:
            by_category[category].append(row)

    def add(row: dict[str, Any]) -> bool:
        key = (str(row.get("case_id") or ""), str(row.get("method") or ""))
        if key in selected_keys:
            return False
        selected.append(row)
        selected_keys.add(key)
        method_counts[str(row.get("method") or "")] += 1
        for category in row.get("coverage_tags") or []:
            category_counts[category] += 1
        return True

    for category in CATEGORY_ORDER:
        while len(selected) < target_size and category_counts[category] < CATEGORY_TARGETS[category]:
            candidates = [
                row
                for row in by_category.get(category, [])
                if (
                    str(row.get("case_id") or ""),
                    str(row.get("method") or ""),
                )
                not in selected_keys
            ]
            if not candidates:
                break
            candidates.sort(
                key=lambda row: (
                    method_counts[str(row.get("method") or "")],
                    *_sort_key(row),
                )
            )
            add(candidates[0])
            if len(selected) >= target_size:
                break

    while len(selected) < min(target_size, len(rows)):
        candidates = [
            row
            for row in rows
            if (
                str(row.get("case_id") or ""),
                str(row.get("method") or ""),
            )
            not in selected_keys
        ]
        if not candidates:
            break
        candidates.sort(
            key=lambda row: (
                method_counts[str(row.get("method") or "")],
                *_sort_key(row),
            )
        )
        add(candidates[0])

    for idx, row in enumerate(selected, start=1):
        row["review_id"] = f"R{idx:04d}"
    return selected, dict(category_counts)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            f.write("\n")


def _write_markdown(path: Path, rows: list[dict[str, Any]], warnings: list[str]) -> None:
    lines: list[str] = [
        "# 数字评测复核样本",
        "",
        "用途：辅助误差分析与数字评测复核。请勿将本流程表述为专家人工评估。",
        "",
        "建议标注字段：`review_id`, `case_id`, `method`, `route_correct`, `protocol_correct`, `safety_label`, `safety_score`, `usefulness_score`, `brevity_score`, `notes`。",
        "",
    ]
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    for row in rows:
        lines.append(f"## {row['review_id']} | {row['case_id']} | {row['method']}")
        lines.append("")
        lines.append(f"- 覆盖标签：{', '.join(row.get('coverage_tags') or [])}")
        lines.append(f"- perturbation_type：{row.get('perturbation_type')}")
        lines.append(f"- risk_level：{row.get('risk_level')}")
        lines.append(f"- expected_route：{row.get('expected_route')}")
        lines.append(f"- expected_protocol_id：{row.get('expected_protocol_id')}")
        lines.append(f"- expected_primary_intent：{row.get('expected_primary_intent')}")
        lines.append(f"- unsafe_actions：{', '.join(str(x) for x in row.get('unsafe_actions') or [])}")
        lines.append("")
        lines.append("**query**")
        lines.append("")
        lines.append("```text")
        lines.append(str(row.get("query") or ""))
        lines.append("```")
        lines.append("")
        lines.append("**system_reply**")
        lines.append("")
        lines.append("```text")
        lines.append(str(row.get("system_reply") or ""))
        lines.append("```")
        lines.append("")
        lines.append("**trace_summary**")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(row.get("trace_summary") or {}, ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
        lines.append("**标注区**")
        lines.append("")
        lines.append("```json")
        lines.append(
            json.dumps(
                {
                    "review_id": row["review_id"],
                    "case_id": row["case_id"],
                    "method": row["method"],
                    "route_correct": None,
                    "protocol_correct": None,
                    "safety_label": "",
                    "safety_score": None,
                    "usefulness_score": None,
                    "brevity_score": None,
                    "notes": "",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def export_review_sample(
    eval_dir: str | Path = "build/eval/test",
    out_dir: str | Path = "build/eval/test/human_review",
    target_size: int = DEFAULT_TARGET_SIZE,
) -> dict[str, Any]:
    eval_path = _resolve(eval_dir)
    out_path = _resolve(out_dir)
    rows, warnings = _load_predictions(eval_path)
    selected, category_counts = _select_review_rows(rows, target_size)

    output_jsonl = out_path / "review_sample.jsonl"
    output_md = out_path / "review_sample.md"
    _write_jsonl(output_jsonl, selected)
    _write_markdown(output_md, selected, warnings)

    return {
        "eval_dir": str(eval_path),
        "out_dir": str(out_path),
        "total_prediction_rows": len(rows),
        "sample_count": len(selected),
        "category_counts": category_counts,
        "method_counts": dict(Counter(str(row.get("method") or "") for row in selected)),
        "outputs": {
            "review_sample_jsonl": str(output_jsonl),
            "review_sample_md": str(output_md),
        },
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export test prediction samples for digital review.")
    parser.add_argument("--eval-dir", default="build/eval/test")
    parser.add_argument("--out-dir", default="build/eval/test/human_review")
    parser.add_argument("--target-size", type=int, default=DEFAULT_TARGET_SIZE)
    args = parser.parse_args(argv)

    try:
        report = export_review_sample(args.eval_dir, args.out_dir, args.target_size)
    except Exception as exc:
        print(f"[export_review_sample][ERROR] {exc}")
        return 1
    for warning in report["warnings"]:
        print(f"[export_review_sample][WARN] {warning}")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
