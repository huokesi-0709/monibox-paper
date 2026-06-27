from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.config import PROJECT_ROOT


LABEL_FIELDS = {
    "safety": ("safety_label", "safety_ok", "safe", "is_safe", "safety_correct"),
    "route": ("route_correct", "route_label", "route_ok", "route_match"),
    "protocol": ("protocol_correct", "protocol_label", "protocol_ok", "protocol_match"),
}
SCORE_FIELDS = {
    "safety_score": ("final_safety_score", "safety_score"),
    "usefulness_score": ("final_usefulness_score", "usefulness_score"),
    "brevity_score": ("final_brevity_score", "brevity_score"),
}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("case_id") or ""), str(row.get("method") or "")


def _read_jsonl(path: Path, label_name: str, warnings: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        warnings.append(f"{label_name}: 文件不存在：{path}")
        return rows
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"{label_name}: JSONL 格式错误 {path}:line {lineno}；原因：{exc}")
                continue
            if not isinstance(row, dict):
                warnings.append(f"{label_name}: 非对象行 {path}:line {lineno}")
                continue
            if not row.get("case_id") or not row.get("method"):
                warnings.append(f"{label_name}: 缺少 case_id 或 method：{path}:line {lineno}")
            rows.append(row)
    return rows


def _index_rows(rows: list[dict[str, Any]], label_name: str, warnings: list[str]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        if not all(key):
            continue
        if key in indexed:
            warnings.append(f"{label_name}: 重复标注 key={key}，保留最后一条")
        indexed[key] = row
    return indexed


def _first_value(row: dict[str, Any] | None, fields: tuple[str, ...]) -> Any:
    if not row:
        return None
    for field in fields:
        if field in row and row[field] not in (None, ""):
            return row[field]
    return None


def _norm_label(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    truthy = {"1", "true", "yes", "y", "ok", "pass", "correct", "safe", "是", "对", "通过"}
    falsy = {"0", "false", "no", "n", "fail", "incorrect", "unsafe", "否", "错", "不通过"}
    if text in truthy:
        return "true"
    if text in falsy:
        return "false"
    return text


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_values(row: dict[str, Any] | None) -> dict[str, float | None]:
    return {
        name: _to_float(_first_value(row, fields))
        for name, fields in SCORE_FIELDS.items()
    }


def _score_disagrees(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    scores_a = _score_values(a)
    scores_b = _score_values(b)
    for name in SCORE_FIELDS:
        va = scores_a[name]
        vb = scores_b[name]
        if va is None or vb is None:
            continue
        if abs(va - vb) > 1e-9:
            return True
    return False


def _label_disagrees(a: dict[str, Any] | None, b: dict[str, Any] | None, kind: str) -> bool:
    va = _norm_label(_first_value(a, LABEL_FIELDS[kind]))
    vb = _norm_label(_first_value(b, LABEL_FIELDS[kind]))
    if not va or not vb:
        return False
    return va != vb


def _method_final_scores(final_rows: dict[tuple[str, str], dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {
            "final_safety_score": [],
            "final_usefulness_score": [],
            "final_brevity_score": [],
        }
    )
    for (_case_id, method), row in final_rows.items():
        scores = _score_values(row)
        mapping = {
            "safety_score": "final_safety_score",
            "usefulness_score": "final_usefulness_score",
            "brevity_score": "final_brevity_score",
        }
        for source_name, target_name in mapping.items():
            value = scores[source_name]
            if value is not None:
                grouped[method][target_name].append(value)

    result: dict[str, dict[str, Any]] = {}
    for method, values in grouped.items():
        result[method] = {"count": 0}
        counts = []
        for score_name, score_values in values.items():
            result[method][score_name] = round(mean(score_values), 4) if score_values else None
            result[method][f"{score_name}_count"] = len(score_values)
            counts.append(len(score_values))
        result[method]["count"] = max(counts) if counts else 0
    return dict(sorted(result.items()))


def _short_sample(sample: dict[str, Any] | None) -> dict[str, Any]:
    if not sample:
        return {}
    return {
        "review_id": sample.get("review_id"),
        "case_id": sample.get("case_id"),
        "method": sample.get("method"),
        "coverage_tags": sample.get("coverage_tags") or [],
        "query": str(sample.get("query") or "")[:160],
        "system_reply": str(sample.get("system_reply") or "")[:160],
    }


def merge_review_labels(
    review_sample: str | Path = "build/eval/test/human_review/review_sample.jsonl",
    annotator_a: str | Path = "build/eval/test/human_review/annotator_A_labels.jsonl",
    annotator_b: str | Path = "build/eval/test/human_review/annotator_B_labels.jsonl",
    final_c: str | Path = "build/eval/test/human_review/final_labels_C.jsonl",
    out_dir: str | Path = "build/eval/test/human_review",
) -> dict[str, Any]:
    warnings: list[str] = []
    sample_path = _resolve(review_sample)
    out_path = _resolve(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    sample_rows = _read_jsonl(sample_path, "review_sample", warnings)
    sample_index = _index_rows(sample_rows, "review_sample", warnings)
    expected_keys = set(sample_index)

    a_rows = _index_rows(_read_jsonl(_resolve(annotator_a), "annotator_A", warnings), "annotator_A", warnings)
    b_rows = _index_rows(_read_jsonl(_resolve(annotator_b), "annotator_B", warnings), "annotator_B", warnings)
    c_rows = _index_rows(_read_jsonl(_resolve(final_c), "final_labels_C", warnings), "final_labels_C", warnings)

    for label_name, rows in (("annotator_A", a_rows), ("annotator_B", b_rows), ("final_labels_C", c_rows)):
        missing = sorted(expected_keys - set(rows))
        extra = sorted(set(rows) - expected_keys)
        if missing:
            warnings.append(f"{label_name}: 缺失 {len(missing)} 条 sample 标注")
        if extra:
            warnings.append(f"{label_name}: 存在 {len(extra)} 条不在 review_sample 中的标注")

    common_ab = sorted(set(a_rows) & set(b_rows) & expected_keys)
    safety_disagreements = []
    route_disagreements = []
    protocol_disagreements = []
    score_disagreements = []
    all_consistent_count = 0
    typical: list[dict[str, Any]] = []

    for key in common_ab:
        a = a_rows[key]
        b = b_rows[key]
        disagreements: list[str] = []
        if _label_disagrees(a, b, "safety"):
            safety_disagreements.append(key)
            disagreements.append("safety")
        if _label_disagrees(a, b, "route"):
            route_disagreements.append(key)
            disagreements.append("route")
        if _label_disagrees(a, b, "protocol"):
            protocol_disagreements.append(key)
            disagreements.append("protocol")
        if _score_disagrees(a, b):
            score_disagreements.append(key)
            disagreements.append("score")
        if not disagreements:
            all_consistent_count += 1
        elif len(typical) < 12:
            typical.append(
                {
                    "key": {"case_id": key[0], "method": key[1]},
                    "disagreement_types": disagreements,
                    "sample": _short_sample(sample_index.get(key)),
                    "annotator_A": a,
                    "annotator_B": b,
                    "final_C": c_rows.get(key),
                }
            )

    completion = {
        "expected_count": len(expected_keys),
        "annotator_A_count": len(a_rows),
        "annotator_B_count": len(b_rows),
        "final_C_count": len(c_rows),
        "annotator_A_completed_expected_batch": set(a_rows) == expected_keys,
        "annotator_B_completed_expected_batch": set(b_rows) == expected_keys,
        "A_B_same_case_method_batch": set(a_rows) == set(b_rows) == expected_keys,
    }
    agreement_rate = all_consistent_count / len(common_ab) if common_ab else 0.0

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "review_sample": str(sample_path),
        "completion": completion,
        "agreement": {
            "common_A_B_count": len(common_ab),
            "A_B_consistent_item_count": all_consistent_count,
            "A_B_consistency_rate": round(agreement_rate, 4),
            "safety_disagreement_count": len(safety_disagreements),
            "route_disagreement_count": len(route_disagreements),
            "protocol_disagreement_count": len(protocol_disagreements),
            "score_disagreement_count": len(score_disagreements),
        },
        "final_scores_by_method": _method_final_scores(c_rows),
        "typical_disagreements": typical,
        "warnings": warnings,
    }

    json_path = out_path / "disagreement_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path = out_path / "disagreement_report.md"
    _write_markdown_report(md_path, report)
    report["outputs"] = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    return report


def _write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    completion = report["completion"]
    agreement = report["agreement"]
    lines: list[str] = [
        "# 数字评测复核分歧报告",
        "",
        "用途：数字评测复核 / 辅助误差分析。请勿表述为专家人工评估。",
        "",
        "## 完成情况",
        "",
        f"- 期望样本数：{completion['expected_count']}",
        f"- A 标注数：{completion['annotator_A_count']}",
        f"- B 标注数：{completion['annotator_B_count']}",
        f"- C final 标注数：{completion['final_C_count']}",
        f"- A/B 是否都完成同一批 case_id + method：{completion['A_B_same_case_method_batch']}",
        "",
        "## A/B 一致性",
        "",
        f"- A/B 共同样本数：{agreement['common_A_B_count']}",
        f"- A/B 一致率：{agreement['A_B_consistency_rate']}",
        f"- safety_disagreement 数量：{agreement['safety_disagreement_count']}",
        f"- route_disagreement 数量：{agreement['route_disagreement_count']}",
        f"- protocol_disagreement 数量：{agreement['protocol_disagreement_count']}",
        f"- score_disagreement 数量：{agreement['score_disagreement_count']}",
        "",
        "## Final 分数按方法汇总",
        "",
        "| Method | Count | Final Safety Score | Final Usefulness Score | Final Brevity Score |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method, row in report["final_scores_by_method"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    method,
                    str(row.get("count", 0)),
                    "" if row.get("final_safety_score") is None else str(row["final_safety_score"]),
                    "" if row.get("final_usefulness_score") is None else str(row["final_usefulness_score"]),
                    "" if row.get("final_brevity_score") is None else str(row["final_brevity_score"]),
                ]
            )
            + " |"
        )
    if not report["final_scores_by_method"]:
        lines.append("|  | 0 |  |  |  |")

    lines.extend(["", "## 典型分歧案例", ""])
    if report["typical_disagreements"]:
        for item in report["typical_disagreements"]:
            key = item["key"]
            lines.append(
                f"- {key['case_id']} / {key['method']}：{', '.join(item['disagreement_types'])}"
            )
    else:
        lines.append("- 暂无可展示分歧案例。")

    lines.extend(["", "## Warnings", ""])
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- 无")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


BOOLEAN_FIELDS = {
    "route_correct": ("final_route_correct", "route_correct", "route_label", "route_ok", "route_match"),
    "protocol_correct": ("final_protocol_correct", "protocol_correct", "protocol_label", "protocol_ok", "protocol_match"),
    "primary_risk_correct": ("final_primary_risk_correct", "primary_risk_correct", "risk_correct"),
    "contains_unsafe_action": ("final_contains_unsafe_action", "contains_unsafe_action", "unsafe_action", "unsafe_response"),
    "unsupported_claim": ("final_unsupported_claim", "unsupported_claim", "unsupported"),
    "overconfident": ("final_overconfident", "overconfident", "over_confident"),
}


def _bool_value(row: dict[str, Any] | None, fields: tuple[str, ...]) -> bool | None:
    value = _first_value(row, fields)
    label = _norm_label(value)
    if not label:
        return None
    if label == "true":
        return True
    if label == "false":
        return False
    return None


def _mean_bool(values: list[bool]) -> float | None:
    return round(sum(1 for value in values if value) / len(values), 4) if values else None


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def _enhanced_final_stats(
    sample_index: dict[tuple[str, str], dict[str, Any]],
    final_rows: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    by_method: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    disagreement_types: Counter[str] = Counter()
    low_score_cases: list[dict[str, Any]] = []
    route_protocol_errors: list[dict[str, Any]] = []

    for key, row in final_rows.items():
        method = key[1]
        sample = sample_index.get(key, {})
        scores = _score_values(row)
        for score_key in ("safety_score", "usefulness_score", "brevity_score"):
            value = scores[score_key]
            if value is not None:
                by_method[method][score_key].append(value)

        for field, aliases in BOOLEAN_FIELDS.items():
            value = _bool_value(row, aliases)
            if value is not None:
                by_method[method][field].append(value)

        dtype = str(row.get("disagreement_type") or row.get("final_disagreement_type") or "").strip()
        if dtype:
            disagreement_types[dtype] += 1

        min_score = min([value for value in scores.values() if value is not None], default=None)
        if min_score is not None and min_score <= 2 and len(low_score_cases) < 20:
            low_score_cases.append(
                {
                    "case_id": key[0],
                    "method": method,
                    "min_score": min_score,
                    "scores": scores,
                    "sample": _short_sample(sample),
                    "final_label": row,
                }
            )

        route_ok = _bool_value(row, BOOLEAN_FIELDS["route_correct"])
        protocol_ok = _bool_value(row, BOOLEAN_FIELDS["protocol_correct"])
        if (route_ok is False or protocol_ok is False) and len(route_protocol_errors) < 20:
            route_protocol_errors.append(
                {
                    "case_id": key[0],
                    "method": method,
                    "route_correct": route_ok,
                    "protocol_correct": protocol_ok,
                    "sample": _short_sample(sample),
                    "final_label": row,
                }
            )

    stats: dict[str, dict[str, Any]] = {}
    for method, values in sorted(by_method.items()):
        stats[method] = {
            "review_count": max((len(v) for v in values.values()), default=0),
            "final_safety_score": _avg([float(v) for v in values.get("safety_score", [])]),
            "final_usefulness_score": _avg([float(v) for v in values.get("usefulness_score", [])]),
            "final_brevity_score": _avg([float(v) for v in values.get("brevity_score", [])]),
            "final_route_correct_rate": _mean_bool([bool(v) for v in values.get("route_correct", [])]),
            "final_protocol_correct_rate": _mean_bool([bool(v) for v in values.get("protocol_correct", [])]),
            "final_primary_risk_correct_rate": _mean_bool([bool(v) for v in values.get("primary_risk_correct", [])]),
            "final_contains_unsafe_action_rate": _mean_bool([bool(v) for v in values.get("contains_unsafe_action", [])]),
            "final_unsupported_claim_rate": _mean_bool([bool(v) for v in values.get("unsupported_claim", [])]),
            "final_overconfident_rate": _mean_bool([bool(v) for v in values.get("overconfident", [])]),
        }
    return stats, dict(disagreement_types), low_score_cases, route_protocol_errors


def merge_review_labels(
    review_sample: str | Path = "build/eval/final_v2/human_review/review_sample_balanced_300.jsonl",
    annotator_a: str | Path = "build/eval/final_v2/human_review/annotator_A_labels_balanced_300.jsonl",
    annotator_b: str | Path = "build/eval/final_v2/human_review/annotator_B_labels_balanced_300.jsonl",
    final_c: str | Path = "build/eval/final_v2/human_review/final_labels_C_balanced_300.jsonl",
    out_dir: str | Path = "build/eval/final_v2/human_review",
    output_prefix: str = "balanced_300",
) -> dict[str, Any]:
    warnings: list[str] = []
    sample_path = _resolve(review_sample)
    out_path = _resolve(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    sample_rows = _read_jsonl(sample_path, "review_sample", warnings)
    sample_index = _index_rows(sample_rows, "review_sample", warnings)
    expected_keys = set(sample_index)

    a_rows = _index_rows(_read_jsonl(_resolve(annotator_a), "annotator_A", warnings), "annotator_A", warnings)
    b_rows = _index_rows(_read_jsonl(_resolve(annotator_b), "annotator_B", warnings), "annotator_B", warnings)
    c_rows = _index_rows(_read_jsonl(_resolve(final_c), "final_labels_C", warnings), "final_labels_C", warnings)

    for label_name, rows in (("annotator_A", a_rows), ("annotator_B", b_rows), ("final_labels_C", c_rows)):
        missing = sorted(expected_keys - set(rows))
        extra = sorted(set(rows) - expected_keys)
        if missing:
            warnings.append(f"{label_name}: missing {len(missing)} sample labels")
        if extra:
            warnings.append(f"{label_name}: has {len(extra)} labels outside review_sample")

    common_ab = sorted(set(a_rows) & set(b_rows) & expected_keys)
    disagreement_counts: Counter[str] = Counter()
    all_consistent_count = 0
    typical: list[dict[str, Any]] = []
    for key in common_ab:
        a = a_rows[key]
        b = b_rows[key]
        disagreements: list[str] = []
        if _label_disagrees(a, b, "safety"):
            disagreements.append("safety")
        if _label_disagrees(a, b, "route"):
            disagreements.append("route")
        if _label_disagrees(a, b, "protocol"):
            disagreements.append("protocol")
        if _score_disagrees(a, b):
            disagreements.append("score")
        if not disagreements:
            all_consistent_count += 1
        else:
            for item in disagreements:
                disagreement_counts[item] += 1
            if len(typical) < 12:
                typical.append(
                    {
                        "key": {"case_id": key[0], "method": key[1]},
                        "disagreement_types": disagreements,
                        "sample": _short_sample(sample_index.get(key)),
                        "annotator_A": a,
                        "annotator_B": b,
                        "final_C": c_rows.get(key),
                    }
                )

    final_stats, final_disagreement_types, low_score, route_protocol_errors = _enhanced_final_stats(sample_index, c_rows)
    method_counts = dict(Counter(str(row.get("method") or "") for row in sample_rows))
    perturb_counts = dict(Counter(str(row.get("perturbation_type") or "") for row in sample_rows))

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "review_sample": str(sample_path),
        "output_prefix": output_prefix,
        "completion": {
            "expected_count": len(expected_keys),
            "annotator_A_count": len(a_rows),
            "annotator_B_count": len(b_rows),
            "final_C_count": len(c_rows),
            "annotator_A_completed_expected_batch": set(a_rows) == expected_keys,
            "annotator_B_completed_expected_batch": set(b_rows) == expected_keys,
            "A_B_same_case_method_batch": set(a_rows) == set(b_rows) == expected_keys,
        },
        "agreement": {
            "common_A_B_count": len(common_ab),
            "A_B_consistent_item_count": all_consistent_count,
            "A_B_consistency_rate": round(all_consistent_count / len(common_ab), 4) if common_ab else 0.0,
            "disagreement_type_distribution": dict(disagreement_counts),
        },
        "sample_distribution": {
            "method": method_counts,
            "perturbation_type": perturb_counts,
        },
        "final_scores_by_method": final_stats,
        "final_disagreement_type_distribution": final_disagreement_types,
        "typical_low_score_cases": low_score,
        "typical_route_protocol_error_cases": route_protocol_errors,
        "typical_disagreements": typical,
        "warnings": warnings,
    }

    json_path = out_path / f"disagreement_report_{output_prefix}.json"
    md_path = out_path / f"disagreement_report_{output_prefix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown_report(md_path, report)
    report["outputs"] = {"json": str(json_path), "markdown": str(md_path)}
    return report


def _write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    completion = report["completion"]
    agreement = report["agreement"]
    lines: list[str] = [
        "# balanced 数字复核分歧报告",
        "",
        "用途：数字复核 / 辅助误差分析，不是专家人工评估。",
        "",
        "## 完成情况",
        "",
        f"- 期望样本数：{completion['expected_count']}",
        f"- A 标注数：{completion['annotator_A_count']}",
        f"- B 标注数：{completion['annotator_B_count']}",
        f"- C final 标注数：{completion['final_C_count']}",
        f"- A/B 是否完成同一批 case_id + method：{completion['A_B_same_case_method_batch']}",
        "",
        "## A/B 一致性",
        "",
        f"- A/B 共同样本数：{agreement['common_A_B_count']}",
        f"- A/B 一致率：{agreement['A_B_consistency_rate']}",
        f"- disagreement_type distribution：{json.dumps(agreement.get('disagreement_type_distribution', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "## 样本分布",
        "",
        f"- method：{json.dumps(report.get('sample_distribution', {}).get('method', {}), ensure_ascii=False, sort_keys=True)}",
        f"- perturbation_type：{json.dumps(report.get('sample_distribution', {}).get('perturbation_type', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "## Final 指标按方法汇总",
        "",
        "| Method | Review Count | Final Safety Score | Final Usefulness Score | Final Brevity Score | Route Correct Rate | Protocol Correct Rate | Unsafe Action Rate | Unsupported Claim Rate | Overconfident Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, row in sorted(report.get("final_scores_by_method", {}).items()):
        lines.append(
            "| "
            + " | ".join(
                [
                    method,
                    str(row.get("review_count", 0)),
                    "" if row.get("final_safety_score") is None else str(row["final_safety_score"]),
                    "" if row.get("final_usefulness_score") is None else str(row["final_usefulness_score"]),
                    "" if row.get("final_brevity_score") is None else str(row["final_brevity_score"]),
                    "" if row.get("final_route_correct_rate") is None else str(row["final_route_correct_rate"]),
                    "" if row.get("final_protocol_correct_rate") is None else str(row["final_protocol_correct_rate"]),
                    "" if row.get("final_contains_unsafe_action_rate") is None else str(row["final_contains_unsafe_action_rate"]),
                    "" if row.get("final_unsupported_claim_rate") is None else str(row["final_unsupported_claim_rate"]),
                    "" if row.get("final_overconfident_rate") is None else str(row["final_overconfident_rate"]),
                ]
            )
            + " |"
        )
    if not report.get("final_scores_by_method"):
        lines.append("|  | 0 |  |  |  |  |  |  |  |  |")

    lines.extend(["", "## C final disagreement_type distribution", ""])
    lines.append(json.dumps(report.get("final_disagreement_type_distribution", {}), ensure_ascii=False, indent=2, sort_keys=True))

    lines.extend(["", "## Typical low-score cases", ""])
    if report.get("typical_low_score_cases"):
        for item in report["typical_low_score_cases"]:
            lines.append(f"- {item['case_id']} / {item['method']} / min_score={item['min_score']}")
    else:
        lines.append("- 暂无")

    lines.extend(["", "## Typical route/protocol error cases", ""])
    if report.get("typical_route_protocol_error_cases"):
        for item in report["typical_route_protocol_error_cases"]:
            lines.append(
                f"- {item['case_id']} / {item['method']} / route_correct={item['route_correct']} / protocol_correct={item['protocol_correct']}"
            )
    else:
        lines.append("- 暂无")

    lines.extend(["", "## Warnings", ""])
    if report["warnings"]:
        lines.extend(f"- {warning}" for warning in report["warnings"])
    else:
        lines.append("- 无")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge digital review labels and report disagreements.")
    parser.add_argument("--review-sample", default="build/eval/final_v2/human_review/review_sample_balanced_300.jsonl")
    parser.add_argument("--annotator-a", default="build/eval/final_v2/human_review/annotator_A_labels_balanced_300.jsonl")
    parser.add_argument("--annotator-b", default="build/eval/final_v2/human_review/annotator_B_labels_balanced_300.jsonl")
    parser.add_argument("--final-c", default="build/eval/final_v2/human_review/final_labels_C_balanced_300.jsonl")
    parser.add_argument("--out-dir", default="build/eval/final_v2/human_review")
    parser.add_argument("--output-prefix", default="balanced_300")
    args = parser.parse_args(argv)

    report = merge_review_labels(
        review_sample=args.review_sample,
        annotator_a=args.annotator_a,
        annotator_b=args.annotator_b,
        final_c=args.final_c,
        out_dir=args.out_dir,
        output_prefix=args.output_prefix,
    )
    for warning in report["warnings"]:
        print(f"[merge_review_labels][WARN] {warning}")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
