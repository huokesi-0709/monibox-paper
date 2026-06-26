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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge digital review labels and report disagreements.")
    parser.add_argument("--review-sample", default="build/eval/test/human_review/review_sample.jsonl")
    parser.add_argument("--annotator-a", default="build/eval/test/human_review/annotator_A_labels.jsonl")
    parser.add_argument("--annotator-b", default="build/eval/test/human_review/annotator_B_labels.jsonl")
    parser.add_argument("--final-c", default="build/eval/test/human_review/final_labels_C.jsonl")
    parser.add_argument("--out-dir", default="build/eval/test/human_review")
    args = parser.parse_args(argv)

    report = merge_review_labels(
        review_sample=args.review_sample,
        annotator_a=args.annotator_a,
        annotator_b=args.annotator_b,
        final_c=args.final_c,
        out_dir=args.out_dir,
    )
    for warning in report["warnings"]:
        print(f"[merge_review_labels][WARN] {warning}")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
