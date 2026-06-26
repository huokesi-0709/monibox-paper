from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from runtime.intent_extractor import INTENT_PRIORITY


DATASET_FILES = (
    ("clean_dev", "dev", "clean", "clean_dev.jsonl"),
    ("robustness_dev", "dev", "robust", "robustness_dev.jsonl"),
    ("clean_test", "test", "clean", "clean_test.jsonl"),
    ("robustness_test", "test", "robust", "robustness_test.jsonl"),
)

REQUIRED_FIELDS = (
    "id",
    "query",
    "canonical_id",
    "clean_query",
    "perturbation_type",
    "risk_level",
    "expected_route",
    "expected_protocol_id",
    "expected_primary_intent",
    "expected_tags",
    "gold_chunk_ids",
    "unsafe_actions",
    "reference_reply",
)

LIST_FIELDS = ("expected_tags", "gold_chunk_ids", "unsafe_actions")
CORE_EVAL_FIELDS = (
    "id",
    "query",
    "canonical_id",
    "clean_query",
    "perturbation_type",
    "risk_level",
    "expected_route",
    "expected_primary_intent",
    "reference_reply",
)
VALID_RISK_LEVELS = ("low", "medium", "high", "critical")
VALID_PERTURBATION_TYPES = ("clean", "filler_noise", "long_context", "repetition")
EXPECTED_TOTAL = 1500
IMBALANCE_MIN_MAX_RATIO = 0.2
GOLD_EMPTY_WARNING_RATIO = 0.5


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _record_label(dataset: str, lineno: int, row: dict[str, Any] | None = None) -> str:
    case_id = ""
    if row is not None:
        value = row.get("id")
        case_id = str(value) if value is not None else ""
    if case_id:
        return f"{dataset}:line {lineno}:{case_id}"
    return f"{dataset}:line {lineno}"


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _percent(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(part * 100.0 / whole, 2)


def _read_jsonl(path: Path, dataset: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    total_lines = 0
    if not path.exists():
        parse_errors.append(
            {
                "dataset": dataset,
                "line": None,
                "id": None,
                "error": f"文件不存在：{path}",
            }
        )
        return rows, parse_errors, total_lines

    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            total_lines += 1
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                parse_errors.append(
                    {
                        "dataset": dataset,
                        "line": lineno,
                        "id": None,
                        "error": f"JSON 解析失败：{exc}",
                    }
                )
                continue
            if not isinstance(payload, dict):
                parse_errors.append(
                    {
                        "dataset": dataset,
                        "line": lineno,
                        "id": None,
                        "error": "该行不是 JSON 对象",
                    }
                )
                continue
            payload["_audit_dataset"] = dataset
            payload["_audit_lineno"] = lineno
            rows.append(payload)
    return rows, parse_errors, total_lines


def _check_row(
    row: dict[str, Any],
    dataset: str,
    known_intents: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    lineno = int(row.get("_audit_lineno") or 0)
    case_id = str(row.get("id") or "")

    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        errors.append(
            {
                "dataset": dataset,
                "line": lineno,
                "id": case_id or None,
                "type": "missing_fields",
                "fields": missing,
                "message": f"{_record_label(dataset, lineno, row)} 缺失字段：{', '.join(missing)}",
            }
        )

    empty_core = [
        field for field in CORE_EVAL_FIELDS if field in row and _is_empty(row.get(field))
    ]
    if empty_core:
        errors.append(
            {
                "dataset": dataset,
                "line": lineno,
                "id": case_id or None,
                "type": "empty_core_fields",
                "fields": empty_core,
                "message": f"{_record_label(dataset, lineno, row)} 核心评测字段为空：{', '.join(empty_core)}",
            }
        )

    for field in LIST_FIELDS:
        if field not in row:
            continue
        value = row.get(field)
        if not isinstance(value, list):
            errors.append(
                {
                    "dataset": dataset,
                    "line": lineno,
                    "id": case_id or None,
                    "type": "invalid_list_field",
                    "field": field,
                    "message": f"{_record_label(dataset, lineno, row)} {field} 必须是 list[str]",
                }
            )
        elif not all(isinstance(item, str) for item in value):
            errors.append(
                {
                    "dataset": dataset,
                    "line": lineno,
                    "id": case_id or None,
                    "type": "invalid_list_item",
                    "field": field,
                    "message": f"{_record_label(dataset, lineno, row)} {field} 包含非字符串元素",
                }
            )

    risk_level = row.get("risk_level")
    if risk_level is not None and str(risk_level) not in VALID_RISK_LEVELS:
        errors.append(
            {
                "dataset": dataset,
                "line": lineno,
                "id": case_id or None,
                "type": "invalid_risk_level",
                "value": risk_level,
                "message": f"{_record_label(dataset, lineno, row)} risk_level 非法：{risk_level}",
            }
        )

    perturbation_type = row.get("perturbation_type")
    if perturbation_type is not None and str(perturbation_type) not in VALID_PERTURBATION_TYPES:
        errors.append(
            {
                "dataset": dataset,
                "line": lineno,
                "id": case_id or None,
                "type": "invalid_perturbation_type",
                "value": perturbation_type,
                "message": f"{_record_label(dataset, lineno, row)} perturbation_type 非法：{perturbation_type}",
            }
        )

    expected_intent = row.get("expected_primary_intent")
    if expected_intent is not None and str(expected_intent) not in known_intents:
        errors.append(
            {
                "dataset": dataset,
                "line": lineno,
                "id": case_id or None,
                "type": "unknown_primary_intent",
                "value": expected_intent,
                "message": f"{_record_label(dataset, lineno, row)} expected_primary_intent 不在已知集合中：{expected_intent}",
            }
        )

    if isinstance(row.get("unsafe_actions"), list) and len(row.get("unsafe_actions") or []) == 0:
        warnings.append(
            {
                "dataset": dataset,
                "line": lineno,
                "id": case_id or None,
                "type": "empty_unsafe_actions",
                "message": f"{_record_label(dataset, lineno, row)} unsafe_actions 为空",
            }
        )

    return errors, warnings


def _counter_for(rows: list[dict[str, Any]], field: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = row.get(field)
        if value is None:
            value = "<missing>"
        elif isinstance(value, str) and not value.strip():
            value = "<empty>"
        else:
            value = str(value)
        counter[value] += 1
    return counter


def _distribution_rows(
    file_stats: dict[str, dict[str, Any]],
    distributions: dict[str, dict[str, Counter[str]]],
    field: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset, split, suite, _filename in DATASET_FILES:
        total = int(file_stats[dataset]["samples"])
        counter = distributions[dataset][field]
        for value in sorted(counter):
            rows.append(
                {
                    "dataset": dataset,
                    "split": split,
                    "suite": suite,
                    "field": field,
                    "value": value,
                    "count": counter[value],
                    "percentage": _percent(counter[value], total),
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _format_count_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def _format_ids(ids: list[str], limit: int | None = None) -> str:
    if not ids:
        return "无"
    shown = ids if limit is None else ids[:limit]
    suffix = ""
    if limit is not None and len(ids) > limit:
        suffix = f"\n\n另有 {len(ids) - limit} 个 ID 详见 dataset_audit.json。"
    return ", ".join(shown) + suffix


def _risk_imbalance_warnings(
    file_stats: dict[str, dict[str, Any]],
    distributions: dict[str, dict[str, Counter[str]]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    overall: Counter[str] = Counter()
    for dataset in distributions:
        overall.update(distributions[dataset]["risk_level"])

    for scope, counter in [("overall", overall)] + [
        (dataset, distributions[dataset]["risk_level"]) for dataset, *_rest in DATASET_FILES
    ]:
        total = sum(counter.values())
        if total == 0:
            continue
        counts = [counter.get(level, 0) for level in VALID_RISK_LEVELS]
        zero_levels = [level for level, count in zip(VALID_RISK_LEVELS, counts) if count == 0]
        positives = [count for count in counts if count > 0]
        min_max_ratio = min(positives) / max(positives) if positives else 0.0
        if zero_levels or min_max_ratio < IMBALANCE_MIN_MAX_RATIO:
            warnings.append(
                {
                    "scope": scope,
                    "type": "risk_distribution_imbalance",
                    "zero_levels": zero_levels,
                    "counts": {level: counter.get(level, 0) for level in VALID_RISK_LEVELS},
                    "min_max_ratio": round(min_max_ratio, 4),
                    "message": (
                        f"{scope} 风险等级分布可能明显失衡"
                        f"（min/max={min_max_ratio:.3f}，缺失类别={zero_levels or '无'}）"
                    ),
                }
            )
    del file_stats
    return warnings


def _build_markdown(report: dict[str, Any]) -> str:
    conclusions = report["conclusions"]
    totals = report["totals"]
    file_stats = report["files"]
    quality = report["quality"]
    warnings = report["warnings"]
    errors = report["errors"]

    lines: list[str] = []
    lines.append("# 数据集审计报告")
    lines.append("")
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 输入目录：`{report['input_dir']}`")
    lines.append(f"- 输出目录：`{report['output_dir']}`")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(
        f"- 数据总量是否为 1500：{'是' if conclusions['total_is_1500'] else '否'}"
        f"（当前 {totals['samples']} 条）。"
    )
    lines.append(
        f"- dev/test 是否泄漏：{'是' if conclusions['has_dev_test_leakage'] else '否'}"
        f"（泄漏 canonical_id 数：{quality['dev_test_leakage_count']}）。"
    )
    lines.append(
        f"- 每个风险类别样本是否明显失衡：{'是' if conclusions['risk_distribution_imbalanced'] else '否'}。"
    )
    lines.append(
        f"- 是否存在字段缺失：{'是' if conclusions['has_missing_fields'] else '否'}"
        f"（字段缺失记录数：{quality['missing_field_record_count']}）。"
    )
    lines.append(
        f"- 是否存在无法参与评测的样本：{'是' if conclusions['has_unusable_samples'] else '否'}"
        f"（严重问题记录数：{quality['serious_issue_count']}）。"
    )
    lines.append(
        f"- 是否可以支撑当前论文的数据集统计：{'是' if conclusions['supports_dataset_statistics'] else '否'}。"
    )
    lines.append(
        f"- gold_chunk_ids 为空比例：{quality['empty_gold_chunk_count']}/{totals['samples']} "
        f"（{quality['empty_gold_chunk_ratio']}%）。"
    )
    if conclusions["evidence_hit_main_conclusion_suitable"]:
        lines.append("- evidence_hit 指标可作为较强证据指标参与主结论。")
    else:
        lines.append(
            "- evidence_hit 指标建议仅作为诊断指标，不宜作为强主结论，原因是 gold_chunk_ids 为空比例过高。"
        )
    lines.append("")
    lines.append("## 文件样本数")
    lines.append("")
    lines.append(
        _format_count_table(
            ["数据文件", "split", "suite", "样本数"],
            [
                [
                    dataset,
                    stats["split"],
                    stats["suite"],
                    stats["samples"],
                ]
                for dataset, stats in file_stats.items()
            ],
        )
    )
    lines.append("")
    lines.append("## 分布摘要")
    lines.append("")
    for title, field, allowed_values in (
        ("风险等级分布", "risk_level", VALID_RISK_LEVELS),
        ("扰动类型分布", "perturbation_type", VALID_PERTURBATION_TYPES),
        ("协议分布", "expected_protocol_id", None),
        ("主意图分布", "expected_primary_intent", INTENT_PRIORITY),
    ):
        lines.append(f"### {title}")
        lines.append("")
        headers = ["数据文件"]
        if allowed_values is None:
            values = sorted(
                {
                    value
                    for dataset in report["distributions"]
                    for value in report["distributions"][dataset][field]
                }
            )
        else:
            values = list(allowed_values)
        headers.extend(values)
        rows = []
        for dataset in report["distributions"]:
            counter = report["distributions"][dataset][field]
            rows.append([dataset, *[counter.get(value, 0) for value in values]])
        lines.append(_format_count_table(headers, rows))
        lines.append("")
    lines.append("## 泄漏与对应关系检查")
    lines.append("")
    lines.append(f"- dev/test canonical_id 泄漏数：{quality['dev_test_leakage_count']}")
    if quality["dev_test_leakage_count"]:
        lines.append(f"- 泄漏 canonical_id：{_format_ids(quality['dev_test_leakage_ids'])}")
    lines.append(f"- robust 样本无法找到 clean 对应项数量：{quality['unmatched_robust_count']}")
    if quality["unmatched_robust_count"]:
        lines.append(f"- 无法对应的 robust 样本：{_format_ids(quality['unmatched_robust_ids'])}")
    lines.append(
        f"- robust 样本只能跨 split 找到 clean 对应项数量：{quality['cross_split_robust_match_count']}"
    )
    if quality["cross_split_robust_match_count"]:
        lines.append(
            f"- 跨 split 对应的 robust 样本：{_format_ids(quality['cross_split_robust_match_ids'])}"
        )
    lines.append("")
    lines.append("## 空字段与安全标注")
    lines.append("")
    lines.append(f"- unsafe_actions 为空样本数：{quality['empty_unsafe_actions_count']}")
    if quality["empty_unsafe_actions_count"]:
        lines.append(f"- unsafe_actions 为空样本 ID：{_format_ids(quality['empty_unsafe_actions_ids'])}")
    lines.append(
        f"- expected_protocol_id 为空样本数：{quality['empty_expected_protocol_id_count']}。"
        "这类样本保留用于 protocol_false_trigger_rate，不按字段缺失处理。"
    )
    lines.append(f"- gold_chunk_ids 为空样本数：{quality['empty_gold_chunk_count']}")
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    if warnings:
        for item in warnings:
            lines.append(f"- [{item.get('type', 'warning')}] {item.get('message', item)}")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## Errors")
    lines.append("")
    if errors:
        for item in errors:
            lines.append(f"- [{item.get('type', 'error')}] {item.get('message', item)}")
    else:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines) + "\n"


def audit_dataset(input_dir: str | Path, output_dir: str | Path) -> tuple[dict[str, Any], int]:
    input_path = _resolve(input_dir)
    output_path = _resolve(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    rows_by_dataset: dict[str, list[dict[str, Any]]] = {}
    file_stats: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    known_intents = set(INTENT_PRIORITY)

    for dataset, split, suite, filename in DATASET_FILES:
        path = input_path / filename
        rows, parse_errors, total_lines = _read_jsonl(path, dataset)
        for parse_error in parse_errors:
            errors.append({**parse_error, "type": "parse_or_file_error", "message": parse_error["error"]})
        rows_by_dataset[dataset] = rows
        all_rows.extend(rows)
        file_stats[dataset] = {
            "path": str(path),
            "split": split,
            "suite": suite,
            "samples": len(rows),
            "non_empty_lines": total_lines,
            "parse_errors": len(parse_errors),
        }
        for row in rows:
            row_errors, row_warnings = _check_row(row, dataset, known_intents)
            errors.extend(row_errors)
            warnings.extend(row_warnings)

    distributions: dict[str, dict[str, Counter[str]]] = {}
    for dataset, rows in rows_by_dataset.items():
        distributions[dataset] = {
            "expected_primary_intent": _counter_for(rows, "expected_primary_intent"),
            "risk_level": _counter_for(rows, "risk_level"),
            "expected_protocol_id": _counter_for(rows, "expected_protocol_id"),
            "perturbation_type": _counter_for(rows, "perturbation_type"),
        }

    id_locations: dict[str, list[str]] = defaultdict(list)
    canonical_by_split: dict[str, dict[str, list[str]]] = {
        "dev": defaultdict(list),
        "test": defaultdict(list),
    }
    clean_ids_by_split: dict[str, set[str]] = {"dev": set(), "test": set()}
    clean_canonical_by_split: dict[str, set[str]] = {"dev": set(), "test": set()}
    clean_ids_all: set[str] = set()
    clean_canonical_all: set[str] = set()

    dataset_meta = {dataset: (split, suite) for dataset, split, suite, _filename in DATASET_FILES}
    for row in all_rows:
        dataset = str(row["_audit_dataset"])
        split, suite = dataset_meta[dataset]
        case_id = str(row.get("id") or "")
        canonical_id = str(row.get("canonical_id") or "")
        if case_id:
            id_locations[case_id].append(dataset)
        if canonical_id:
            canonical_by_split[split][canonical_id].append(case_id)
        if suite == "clean":
            if case_id:
                clean_ids_by_split[split].add(case_id)
                clean_ids_all.add(case_id)
            if canonical_id:
                clean_canonical_by_split[split].add(canonical_id)
                clean_canonical_all.add(canonical_id)

    duplicate_ids = sorted(case_id for case_id, locations in id_locations.items() if len(locations) > 1)
    for case_id in duplicate_ids:
        errors.append(
            {
                "type": "duplicate_id",
                "id": case_id,
                "locations": id_locations[case_id],
                "message": f"样本 ID 重复：{case_id}，位置：{', '.join(id_locations[case_id])}",
            }
        )

    dev_canonical = set(canonical_by_split["dev"])
    test_canonical = set(canonical_by_split["test"])
    leakage_ids = sorted(dev_canonical & test_canonical)
    leakage_rows: list[dict[str, Any]] = []
    for canonical_id in leakage_ids:
        leakage_rows.append(
            {
                "canonical_id": canonical_id,
                "status": "leakage",
                "dev_ids": ";".join(sorted(canonical_by_split["dev"][canonical_id])),
                "test_ids": ";".join(sorted(canonical_by_split["test"][canonical_id])),
            }
        )
        errors.append(
            {
                "type": "dev_test_leakage",
                "canonical_id": canonical_id,
                "message": f"canonical_id {canonical_id} 同时出现在 dev 和 test",
            }
        )
    if not leakage_rows:
        leakage_rows.append(
            {
                "canonical_id": "",
                "status": "no_leakage",
                "dev_ids": "",
                "test_ids": "",
            }
        )

    unmatched_robust_ids: list[str] = []
    cross_split_robust_match_ids: list[str] = []
    for dataset, split, suite, _filename in DATASET_FILES:
        if suite != "robust":
            continue
        for row in rows_by_dataset[dataset]:
            case_id = str(row.get("id") or "")
            clean_id = str(row.get("clean_id") or "")
            canonical_id = str(row.get("canonical_id") or "")
            matched_all = (
                (clean_id and clean_id in clean_ids_all)
                or (canonical_id and canonical_id in clean_canonical_all)
                or (canonical_id and canonical_id in clean_ids_all)
            )
            matched_same_split = (
                (clean_id and clean_id in clean_ids_by_split[split])
                or (canonical_id and canonical_id in clean_canonical_by_split[split])
                or (canonical_id and canonical_id in clean_ids_by_split[split])
            )
            if not matched_all:
                unmatched_robust_ids.append(case_id)
                errors.append(
                    {
                        "type": "unmatched_robust_clean",
                        "dataset": dataset,
                        "id": case_id,
                        "clean_id": clean_id or None,
                        "canonical_id": canonical_id or None,
                        "message": f"robust 样本 {case_id} 找不到对应 clean 样本",
                    }
                )
            elif not matched_same_split:
                cross_split_robust_match_ids.append(case_id)
                errors.append(
                    {
                        "type": "cross_split_robust_clean_match",
                        "dataset": dataset,
                        "id": case_id,
                        "clean_id": clean_id or None,
                        "canonical_id": canonical_id or None,
                        "message": f"robust 样本 {case_id} 只能在 {split} 以外找到 clean 对应项",
                    }
                )

    risk_warnings = _risk_imbalance_warnings(file_stats, distributions)
    warnings.extend(risk_warnings)

    empty_unsafe_ids = sorted(
        str(row.get("id") or "")
        for row in all_rows
        if isinstance(row.get("unsafe_actions"), list) and len(row.get("unsafe_actions") or []) == 0
    )
    empty_gold_ids = sorted(
        str(row.get("id") or "")
        for row in all_rows
        if isinstance(row.get("gold_chunk_ids"), list) and len(row.get("gold_chunk_ids") or []) == 0
    )
    empty_protocol_ids = sorted(
        str(row.get("id") or "")
        for row in all_rows
        if "expected_protocol_id" in row and _is_empty(row.get("expected_protocol_id"))
    )
    total_samples = len(all_rows)
    empty_gold_ratio = _percent(len(empty_gold_ids), total_samples)
    if total_samples and len(empty_gold_ids) / total_samples > GOLD_EMPTY_WARNING_RATIO:
        warnings.append(
            {
                "type": "high_empty_gold_chunk_ratio",
                "message": (
                    f"gold_chunk_ids 为空比例为 {empty_gold_ratio}%；"
                    "evidence_hit 应仅作为诊断指标，不宜作为强主结论"
                ),
                "empty_count": len(empty_gold_ids),
                "total": total_samples,
                "ratio": empty_gold_ratio,
            }
        )

    if total_samples != EXPECTED_TOTAL:
        errors.append(
            {
                "type": "unexpected_total_samples",
                "message": f"数据集总量为 {total_samples}，期望为 {EXPECTED_TOTAL}",
                "actual": total_samples,
                "expected": EXPECTED_TOTAL,
            }
        )

    missing_field_record_count = sum(1 for item in errors if item.get("type") == "missing_fields")
    serious_issue_count = len(errors)
    risk_distribution_imbalanced = any(
        item.get("type") == "risk_distribution_imbalance" for item in warnings
    )
    supports_dataset_statistics = (
        total_samples == EXPECTED_TOTAL
        and not leakage_ids
        and serious_issue_count == 0
    )

    serializable_distributions = {
        dataset: {field: dict(counter) for field, counter in fields.items()}
        for dataset, fields in distributions.items()
    }
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_dir": str(input_path),
        "output_dir": str(output_path),
        "expected_total": EXPECTED_TOTAL,
        "totals": {
            "samples": total_samples,
            "files": len(DATASET_FILES),
        },
        "files": file_stats,
        "known_intents": list(INTENT_PRIORITY),
        "valid_risk_levels": list(VALID_RISK_LEVELS),
        "valid_perturbation_types": list(VALID_PERTURBATION_TYPES),
        "distributions": serializable_distributions,
        "quality": {
            "missing_field_record_count": missing_field_record_count,
            "serious_issue_count": serious_issue_count,
            "dev_test_leakage_count": len(leakage_ids),
            "dev_test_leakage_ids": leakage_ids,
            "unmatched_robust_count": len(unmatched_robust_ids),
            "unmatched_robust_ids": sorted(unmatched_robust_ids),
            "cross_split_robust_match_count": len(cross_split_robust_match_ids),
            "cross_split_robust_match_ids": sorted(cross_split_robust_match_ids),
            "duplicate_id_count": len(duplicate_ids),
            "duplicate_ids": duplicate_ids,
            "empty_unsafe_actions_count": len(empty_unsafe_ids),
            "empty_unsafe_actions_ids": empty_unsafe_ids,
            "empty_expected_protocol_id_count": len(empty_protocol_ids),
            "empty_expected_protocol_id_ids": empty_protocol_ids,
            "empty_gold_chunk_count": len(empty_gold_ids),
            "empty_gold_chunk_ratio": empty_gold_ratio,
            "empty_gold_chunk_ids_sample": empty_gold_ids[:100],
        },
        "conclusions": {
            "total_is_1500": total_samples == EXPECTED_TOTAL,
            "has_dev_test_leakage": bool(leakage_ids),
            "risk_distribution_imbalanced": risk_distribution_imbalanced,
            "has_missing_fields": missing_field_record_count > 0,
            "has_unusable_samples": serious_issue_count > 0,
            "supports_dataset_statistics": supports_dataset_statistics,
            "evidence_hit_main_conclusion_suitable": empty_gold_ratio <= (GOLD_EMPTY_WARNING_RATIO * 100.0),
        },
        "warnings": warnings,
        "errors": errors,
    }

    distribution_fieldnames = ["dataset", "split", "suite", "field", "value", "count", "percentage"]
    _write_csv(
        output_path / "distribution_by_intent.csv",
        _distribution_rows(file_stats, distributions, "expected_primary_intent"),
        distribution_fieldnames,
    )
    _write_csv(
        output_path / "distribution_by_risk.csv",
        _distribution_rows(file_stats, distributions, "risk_level"),
        distribution_fieldnames,
    )
    _write_csv(
        output_path / "distribution_by_perturbation.csv",
        _distribution_rows(file_stats, distributions, "perturbation_type"),
        distribution_fieldnames,
    )
    _write_csv(
        output_path / "leakage_check.csv",
        leakage_rows,
        ["canonical_id", "status", "dev_ids", "test_ids"],
    )

    json_path = output_path / "dataset_audit.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path = output_path / "dataset_audit.md"
    md_path.write_text(_build_markdown(report), encoding="utf-8")
    return report, 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit HSC-RAG benchmark datasets.")
    parser.add_argument("--input-dir", default="benchmarks/data", help="Directory containing benchmark JSONL files.")
    parser.add_argument("--output-dir", default="build/eval/dataset_audit", help="Directory for audit outputs.")
    args = parser.parse_args(argv)

    report, exit_code = audit_dataset(args.input_dir, args.output_dir)
    output_dir = Path(report["output_dir"])
    print(f"数据集审计 Markdown：{output_dir / 'dataset_audit.md'}")
    print(f"数据集审计 JSON：{output_dir / 'dataset_audit.json'}")
    print(f"严重问题数：{report['quality']['serious_issue_count']}")
    print(f"警告数：{len(report['warnings'])}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
