from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from runtime.intent_extractor import INTENT_PRIORITY


DATA_DIR = PROJECT_ROOT / "benchmarks" / "data_v2"
DATASET_FILES = (
    ("clean_dev", "dev", "clean", "clean_dev.jsonl", 500),
    ("robustness_dev", "dev", "robust", "robustness_dev.jsonl", 1500),
    ("clean_test", "test", "clean", "clean_test.jsonl", 1000),
    ("robustness_test", "test", "robust", "robustness_test.jsonl", 3000),
)
EXPECTED_TOTAL = 6000
REQUIRED_FIELDS = (
    "id",
    "canonical_id",
    "clean_id",
    "query",
    "clean_query",
    "perturbation_type",
    "expected_primary_intent",
    "expected_route",
    "expected_protocol_id",
    "expected_tags",
    "risk_level",
    "gold_chunk_ids",
    "unsafe_actions",
    "reference_reply",
    "scenario_family",
    "body_part",
    "hazard_context",
    "evidence_level",
    "generation_source",
    "split",
)
LIST_FIELDS = ("expected_tags", "gold_chunk_ids", "unsafe_actions")
CORE_STRING_FIELDS = (
    "id",
    "canonical_id",
    "clean_id",
    "query",
    "clean_query",
    "perturbation_type",
    "expected_primary_intent",
    "expected_route",
    "risk_level",
    "reference_reply",
    "scenario_family",
    "body_part",
    "hazard_context",
    "evidence_level",
    "generation_source",
    "split",
)
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
VALID_PERTURBATION_TYPES = {"clean", "filler_noise", "long_context", "repetition"}
ROBUST_TYPES = {"filler_noise", "long_context", "repetition"}
VALID_EVIDENCE_LEVELS = {"low", "medium", "high"}
EXPECTED_CATEGORY_COUNTS = {
    "severe_bleeding": 150,
    "respiratory_distress": 120,
    "crush_trapped": 120,
    "fracture_immobility": 90,
    "head_injury_consciousness": 100,
    "hypothermia": 90,
    "dehydration_hunger": 70,
    "smoke_dust_choking": 80,
    "structural_danger_aftershock": 90,
    "sos_location_device": 80,
    "psychological_panic": 70,
    "unsafe_request": 90,
    "negation_conflict": 100,
    "multi_intent_priority": 150,
    "out_of_scope_low_evidence": 100,
}


def _read_jsonl(
    path: Path, dataset: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    total_lines = 0
    if not path.exists():
        errors.append(
            {
                "type": "missing_file",
                "dataset": dataset,
                "path": str(path),
                "message": f"file not found: {path}",
            }
        )
        return rows, errors, total_lines

    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            total_lines += 1
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(
                    {
                        "type": "json_parse_error",
                        "dataset": dataset,
                        "line": lineno,
                        "message": str(exc),
                    }
                )
                continue
            if not isinstance(payload, dict):
                errors.append(
                    {
                        "type": "not_json_object",
                        "dataset": dataset,
                        "line": lineno,
                        "message": "row is not a JSON object",
                    }
                )
                continue
            payload["_audit_dataset"] = dataset
            payload["_audit_lineno"] = lineno
            rows.append(payload)
    return rows, errors, total_lines


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _check_row(
    row: dict[str, Any],
    dataset: str,
    expected_split: str,
    expected_suite: str,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    case_id = str(row.get("id") or "")
    lineno = int(row.get("_audit_lineno") or 0)

    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        errors.append(
            {
                "type": "missing_fields",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "fields": missing,
                "message": f"{case_id} missing fields: {', '.join(missing)}",
            }
        )

    empty = [field for field in CORE_STRING_FIELDS if field in row and _is_empty(row[field])]
    if empty:
        errors.append(
            {
                "type": "empty_core_fields",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "fields": empty,
                "message": f"{case_id} has empty core fields: {', '.join(empty)}",
            }
        )

    for field in LIST_FIELDS:
        if field not in row:
            continue
        value = row[field]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(
                {
                    "type": "invalid_list_field",
                    "dataset": dataset,
                    "line": lineno,
                    "id": case_id,
                    "field": field,
                    "message": f"{case_id} {field} must be list[str]",
                }
            )

    risk = row.get("risk_level")
    if risk not in VALID_RISK_LEVELS:
        errors.append(
            {
                "type": "invalid_risk_level",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": risk,
                "message": f"{case_id} invalid risk_level: {risk}",
            }
        )

    perturbation = row.get("perturbation_type")
    if perturbation not in VALID_PERTURBATION_TYPES:
        errors.append(
            {
                "type": "invalid_perturbation_type",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": perturbation,
                "message": f"{case_id} invalid perturbation_type: {perturbation}",
            }
        )
    elif expected_suite == "clean" and perturbation != "clean":
        errors.append(
            {
                "type": "unexpected_clean_perturbation",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": perturbation,
                "message": f"{case_id} in clean file has perturbation {perturbation}",
            }
        )
    elif expected_suite == "robust" and perturbation not in ROBUST_TYPES:
        errors.append(
            {
                "type": "unexpected_robust_perturbation",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": perturbation,
                "message": f"{case_id} in robust file has perturbation {perturbation}",
            }
        )

    intent = row.get("expected_primary_intent")
    if intent not in set(INTENT_PRIORITY):
        errors.append(
            {
                "type": "unknown_primary_intent",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": intent,
                "message": f"{case_id} unknown expected_primary_intent: {intent}",
            }
        )

    split = row.get("split")
    if split != expected_split:
        errors.append(
            {
                "type": "split_mismatch",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": split,
                "expected": expected_split,
                "message": f"{case_id} split={split}, expected {expected_split}",
            }
        )

    evidence = row.get("evidence_level")
    if evidence not in VALID_EVIDENCE_LEVELS:
        errors.append(
            {
                "type": "invalid_evidence_level",
                "dataset": dataset,
                "line": lineno,
                "id": case_id,
                "value": evidence,
                "message": f"{case_id} invalid evidence_level: {evidence}",
            }
        )

    if row.get("scenario_family") == "unsafe_request":
        unsafe_actions = row.get("unsafe_actions")
        if not isinstance(unsafe_actions, list) or not unsafe_actions:
            errors.append(
                {
                    "type": "unsafe_request_empty_unsafe_actions",
                    "dataset": dataset,
                    "line": lineno,
                    "id": case_id,
                    "message": f"{case_id} unsafe_request must include unsafe_actions",
                }
            )

    if risk in {"high", "critical"}:
        unsafe_actions = row.get("unsafe_actions")
        if not isinstance(unsafe_actions, list) or not unsafe_actions:
            errors.append(
                {
                    "type": "high_critical_empty_unsafe_actions",
                    "dataset": dataset,
                    "line": lineno,
                    "id": case_id,
                    "risk_level": risk,
                    "message": f"{case_id} high/critical sample has empty unsafe_actions",
                }
            )
    return errors


def _normalize_query(text: str) -> str:
    return re.sub(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()\[\]【】]+", "", text).lower()


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _distribution_rows(
    rows_by_dataset: dict[str, list[dict[str, Any]]], field: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    meta = {name: (split, suite) for name, split, suite, _filename, _expected in DATASET_FILES}
    for dataset in [item[0] for item in DATASET_FILES]:
        rows = rows_by_dataset[dataset]
        counter = Counter(str(row.get(field) or "<missing>") for row in rows)
        total = len(rows)
        split, suite = meta[dataset]
        for value, count in sorted(counter.items()):
            out.append(
                {
                    "dataset": dataset,
                    "split": split,
                    "suite": suite,
                    "value": value,
                    "count": count,
                    "percentage": round(count * 100.0 / total, 4) if total else 0.0,
                }
            )
    return out


def _leakage_rows(
    canonical_by_split: dict[str, dict[str, list[str]]]
) -> list[dict[str, Any]]:
    leakage = sorted(set(canonical_by_split["dev"]) & set(canonical_by_split["test"]))
    if not leakage:
        return [
            {
                "canonical_id": "",
                "status": "no_leakage",
                "dev_ids": "",
                "test_ids": "",
            }
        ]
    return [
        {
            "canonical_id": canonical_id,
            "status": "leakage",
            "dev_ids": ";".join(sorted(canonical_by_split["dev"][canonical_id])),
            "test_ids": ";".join(sorted(canonical_by_split["test"][canonical_id])),
        }
        for canonical_id in leakage
    ]


def _build_markdown(report: dict[str, Any]) -> str:
    quality = report["quality"]
    lines = [
        "# HSC-DisasterBench-v2 Dataset Audit",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Input dir: `{report['input_dir']}`",
        f"- Passed: `{report['passed']}`",
        f"- Serious issue count: {quality['serious_issue_count']}",
        f"- Total samples: {report['totals']['samples']} / {report['expected_total']}",
        f"- Dev/test leakage count: {quality['dev_test_leakage_count']}",
        f"- Missing-field record count: {quality['missing_field_record_count']}",
        f"- Exact duplicate query rate: {quality['exact_duplicate_query_rate']}%",
        f"- Normalized duplicate query rate: {quality['normalized_duplicate_query_rate']}%",
        "",
        "## File Counts",
        "",
        "| file | actual | expected |",
        "|---|---:|---:|",
    ]
    for item in report["files"]:
        lines.append(f"| {item['filename']} | {item['rows']} | {item['expected_rows']} |")

    lines.extend(["", "## Canonical Scenario Distribution", "", "| scenario_family | clean_count | expected |", "|---|---:|---:|"])
    category_counts = report["canonical_category_distribution"]
    for family, expected in EXPECTED_CATEGORY_COUNTS.items():
        lines.append(f"| {family} | {category_counts.get(family, 0)} | {expected} |")

    lines.extend(["", "## Risk Distribution", "", "| risk_level | count |", "|---|---:|"])
    for risk, count in report["risk_distribution"].items():
        lines.append(f"| {risk} | {count} |")

    lines.extend(["", "## Perturbation Distribution", "", "| perturbation_type | count |", "|---|---:|"])
    for perturbation, count in report["perturbation_distribution"].items():
        lines.append(f"| {perturbation} | {count} |")

    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in report["errors"][:100]:
            lines.append(f"- [{error.get('type')}] {error.get('message')}")
        if len(report["errors"]) > 100:
            lines.append(f"- ... {len(report['errors']) - 100} more errors omitted")
    else:
        lines.extend(["", "## Errors", "", "- None"])

    lines.append("")
    return "\n".join(lines)


def audit_dataset() -> tuple[dict[str, Any], int]:
    rows_by_dataset: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    for dataset, split, suite, filename, expected_rows in DATASET_FILES:
        path = DATA_DIR / filename
        rows, read_errors, total_lines = _read_jsonl(path, dataset)
        rows_by_dataset[dataset] = rows
        all_rows.extend(rows)
        errors.extend(read_errors)
        files.append(
            {
                "dataset": dataset,
                "filename": filename,
                "split": split,
                "suite": suite,
                "rows": len(rows),
                "non_empty_lines": total_lines,
                "expected_rows": expected_rows,
                "matches_expected": len(rows) == expected_rows,
            }
        )
        if len(rows) != expected_rows:
            errors.append(
                {
                    "type": "unexpected_file_count",
                    "dataset": dataset,
                    "message": f"{filename} has {len(rows)} rows, expected {expected_rows}",
                    "actual": len(rows),
                    "expected": expected_rows,
                }
            )
        for row in rows:
            errors.extend(_check_row(row, dataset, split, suite))

    id_locations: dict[str, list[str]] = defaultdict(list)
    canonical_by_split: dict[str, dict[str, list[str]]] = {
        "dev": defaultdict(list),
        "test": defaultdict(list),
    }
    clean_by_canonical: dict[str, dict[str, Any]] = {}
    robust_by_canonical: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in all_rows:
        dataset = str(row["_audit_dataset"])
        case_id = str(row.get("id") or "")
        canonical_id = str(row.get("canonical_id") or "")
        split = str(row.get("split") or "")
        perturbation = str(row.get("perturbation_type") or "")
        if case_id:
            id_locations[case_id].append(dataset)
        if split in canonical_by_split and canonical_id:
            canonical_by_split[split][canonical_id].append(case_id)
        if perturbation == "clean":
            if canonical_id in clean_by_canonical:
                errors.append(
                    {
                        "type": "duplicate_clean_canonical",
                        "id": case_id,
                        "canonical_id": canonical_id,
                        "message": f"canonical_id {canonical_id} has duplicate clean samples",
                    }
                )
            clean_by_canonical[canonical_id] = row
        elif perturbation in ROBUST_TYPES:
            robust_by_canonical[canonical_id].append(row)

    duplicate_ids = sorted(case_id for case_id, locations in id_locations.items() if len(locations) > 1)
    for case_id in duplicate_ids:
        errors.append(
            {
                "type": "duplicate_id",
                "id": case_id,
                "message": f"duplicate id: {case_id}",
                "locations": id_locations[case_id],
            }
        )

    leakage = sorted(set(canonical_by_split["dev"]) & set(canonical_by_split["test"]))
    for canonical_id in leakage:
        errors.append(
            {
                "type": "dev_test_leakage",
                "canonical_id": canonical_id,
                "message": f"canonical_id appears in both dev and test: {canonical_id}",
            }
        )

    for canonical_id, clean in clean_by_canonical.items():
        robust_rows = robust_by_canonical.get(canonical_id, [])
        variants = Counter(str(row.get("perturbation_type") or "") for row in robust_rows)
        if variants != Counter({"filler_noise": 1, "long_context": 1, "repetition": 1}):
            errors.append(
                {
                    "type": "incomplete_robust_variants",
                    "canonical_id": canonical_id,
                    "id": clean.get("id"),
                    "variants": dict(variants),
                    "message": f"{canonical_id} robust variants are incomplete: {dict(variants)}",
                }
            )
        clean_split = clean.get("split")
        for robust in robust_rows:
            if robust.get("split") != clean_split:
                errors.append(
                    {
                        "type": "robust_split_mismatch",
                        "canonical_id": canonical_id,
                        "id": robust.get("id"),
                        "message": f"{robust.get('id')} split differs from clean sample",
                    }
                )

    orphan_robust = sorted(set(robust_by_canonical) - set(clean_by_canonical))
    for canonical_id in orphan_robust:
        errors.append(
            {
                "type": "orphan_robust_canonical",
                "canonical_id": canonical_id,
                "message": f"robust samples have no clean canonical: {canonical_id}",
            }
        )

    total_samples = len(all_rows)
    if total_samples != EXPECTED_TOTAL:
        errors.append(
            {
                "type": "unexpected_total_count",
                "message": f"total samples = {total_samples}, expected {EXPECTED_TOTAL}",
                "actual": total_samples,
                "expected": EXPECTED_TOTAL,
            }
        )

    clean_rows = list(clean_by_canonical.values())
    category_counts = Counter(str(row.get("scenario_family") or "<missing>") for row in clean_rows)
    for family, expected in EXPECTED_CATEGORY_COUNTS.items():
        actual = category_counts.get(family, 0)
        if actual != expected:
            errors.append(
                {
                    "type": "unexpected_category_count",
                    "scenario_family": family,
                    "actual": actual,
                    "expected": expected,
                    "message": f"{family} clean count = {actual}, expected {expected}",
                }
            )

    exact_query_counts = Counter(str(row.get("query") or "") for row in all_rows)
    normalized_query_counts = Counter(_normalize_query(str(row.get("query") or "")) for row in all_rows)
    exact_duplicate_rows = sum(count for count in exact_query_counts.values() if count > 1)
    normalized_duplicate_rows = sum(count for count in normalized_query_counts.values() if count > 1)
    if exact_duplicate_rows:
        errors.append(
            {
                "type": "exact_duplicate_queries",
                "message": f"exact duplicate query rows: {exact_duplicate_rows}",
                "duplicate_rows": exact_duplicate_rows,
            }
        )
    if normalized_duplicate_rows:
        errors.append(
            {
                "type": "normalized_duplicate_queries",
                "message": f"normalized duplicate query rows: {normalized_duplicate_rows}",
                "duplicate_rows": normalized_duplicate_rows,
            }
        )

    missing_field_record_count = sum(1 for item in errors if item.get("type") == "missing_fields")
    leakage_rows = _leakage_rows(canonical_by_split)
    serious_issue_count = len(errors)
    passed = serious_issue_count == 0

    risk_distribution = Counter(str(row.get("risk_level") or "<missing>") for row in all_rows)
    perturbation_distribution = Counter(
        str(row.get("perturbation_type") or "<missing>") for row in all_rows
    )

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_dir": str(DATA_DIR),
        "expected_total": EXPECTED_TOTAL,
        "passed": passed,
        "files": files,
        "totals": {
            "samples": total_samples,
            "canonical_clean_samples": len(clean_rows),
            "robust_samples": total_samples - len(clean_rows),
        },
        "canonical_category_distribution": dict(category_counts),
        "risk_distribution": dict(sorted(risk_distribution.items())),
        "perturbation_distribution": dict(sorted(perturbation_distribution.items())),
        "quality": {
            "serious_issue_count": serious_issue_count,
            "missing_field_record_count": missing_field_record_count,
            "dev_test_leakage_count": len(leakage),
            "dev_test_leakage_ids": leakage,
            "duplicate_id_count": len(duplicate_ids),
            "duplicate_ids": duplicate_ids,
            "orphan_robust_canonical_count": len(orphan_robust),
            "orphan_robust_canonical_ids": orphan_robust,
            "exact_duplicate_query_rows": exact_duplicate_rows,
            "exact_duplicate_query_rate": round(exact_duplicate_rows * 100.0 / total_samples, 4)
            if total_samples
            else 0.0,
            "normalized_duplicate_query_rows": normalized_duplicate_rows,
            "normalized_duplicate_query_rate": round(
                normalized_duplicate_rows * 100.0 / total_samples, 4
            )
            if total_samples
            else 0.0,
        },
        "errors": errors,
    }

    _write_csv(
        DATA_DIR / "distribution_by_category.csv",
        _distribution_rows(rows_by_dataset, "scenario_family"),
        ["dataset", "split", "suite", "value", "count", "percentage"],
    )
    _write_csv(
        DATA_DIR / "distribution_by_risk.csv",
        _distribution_rows(rows_by_dataset, "risk_level"),
        ["dataset", "split", "suite", "value", "count", "percentage"],
    )
    _write_csv(
        DATA_DIR / "distribution_by_perturbation.csv",
        _distribution_rows(rows_by_dataset, "perturbation_type"),
        ["dataset", "split", "suite", "value", "count", "percentage"],
    )
    _write_csv(
        DATA_DIR / "leakage_check.csv",
        leakage_rows,
        ["canonical_id", "status", "dev_ids", "test_ids"],
    )
    (DATA_DIR / "dataset_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (DATA_DIR / "dataset_audit.md").write_text(_build_markdown(report), encoding="utf-8")
    return report, 0 if passed else 1


def main() -> int:
    report, exit_code = audit_dataset()
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "total": report["totals"]["samples"],
                "serious_issue_count": report["quality"]["serious_issue_count"],
                "dev_test_leakage_count": report["quality"]["dev_test_leakage_count"],
                "dataset_audit": str(DATA_DIR / "dataset_audit.md"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
