from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from experiments.final_v2_utils import (
    ABLATIONS,
    DATA_V2_DIR,
    FINAL_V2_DIR,
    MAIN_METHODS,
    count_jsonl,
    read_json,
    read_jsonl,
    sha256_file,
    write_json,
)


EXPECTED_DATA_COUNTS = {
    "clean_dev.jsonl": 500,
    "robustness_dev.jsonl": 1500,
    "clean_test.jsonl": 1000,
    "robustness_test.jsonl": 3000,
}
EXPECTED_PERTURBATION = {
    "clean": 75,
    "filler_noise": 75,
    "long_context": 75,
    "repetition": 75,
}
EXPECTED_METHOD_REVIEW = {method: 75 for method in MAIN_METHODS}
REQUIRED_FIELDS = {
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
}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path)


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": _rel(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else "",
    }


def _add_file_check(
    checks: list[dict[str, Any]],
    errors: list[str],
    path: Path,
    label: str,
    critical: bool = True,
) -> None:
    record = {"label": label, **_file_record(path)}
    checks.append(record)
    if critical and not path.exists():
        errors.append(f"missing required file: {label} ({_rel(path)})")


def _load_all_dataset_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filename in EXPECTED_DATA_COUNTS:
        rows.extend(read_jsonl(DATA_V2_DIR / filename))
    return rows


def _validate_dataset(errors: list[str], warnings: list[str]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for filename, expected in EXPECTED_DATA_COUNTS.items():
        path = DATA_V2_DIR / filename
        count = count_jsonl(path)
        files[filename] = {**_file_record(path), "samples": count, "expected": expected}
        if not path.exists():
            errors.append(f"dataset file missing: {_rel(path)}")
        elif count != expected:
            errors.append(f"dataset count mismatch: {filename} expected {expected}, got {count}")

    audit = read_json(DATA_V2_DIR / "dataset_audit.json")
    audit_passed = bool(audit.get("passed")) if audit else False
    if audit and not audit_passed:
        errors.append("dataset_audit.json reports passed=false")
    if not audit:
        warnings.append("dataset_audit.json missing; validation used direct JSONL checks only")

    rows = _load_all_dataset_rows()
    total = len(rows)
    if total != 6000:
        errors.append(f"dataset total mismatch: expected 6000, got {total}")

    missing_field_count = 0
    high_critical_empty_unsafe = 0
    exact_queries = Counter()
    normalized_queries = Counter()
    dev_ids: set[str] = set()
    test_ids: set[str] = set()
    robust_by_clean: dict[str, set[str]] = defaultdict(set)
    clean_ids: set[str] = set()
    scenario_counts = Counter()
    risk_counts = Counter()

    for row in rows:
        missing = REQUIRED_FIELDS.difference(row)
        if missing:
            missing_field_count += 1
        risk = str(row.get("risk_level") or "")
        risk_counts[risk] += 1
        scenario_counts[str(row.get("scenario_family") or "")] += 1
        if risk in {"high", "critical"} and not row.get("unsafe_actions"):
            high_critical_empty_unsafe += 1
        query = str(row.get("query") or "")
        exact_queries[query] += 1
        normalized_queries["".join(query.split()).lower()] += 1
        canonical_id = str(row.get("canonical_id") or "")
        if row.get("split") == "dev":
            dev_ids.add(canonical_id)
        elif row.get("split") == "test":
            test_ids.add(canonical_id)
        perturbation = str(row.get("perturbation_type") or "")
        clean_id = str(row.get("clean_id") or row.get("id") or "")
        if perturbation == "clean":
            clean_ids.add(clean_id)
        else:
            robust_by_clean[clean_id].add(perturbation)

    leakage = sorted(dev_ids.intersection(test_ids))
    if leakage:
        errors.append(f"dev/test canonical_id leakage: {len(leakage)} ids")
    if missing_field_count:
        errors.append(f"dataset field completeness failed: {missing_field_count} records missing fields")
    if high_critical_empty_unsafe:
        warnings.append(f"high/critical records with empty unsafe_actions: {high_critical_empty_unsafe}")

    missing_robust = [
        clean_id
        for clean_id in sorted(clean_ids)
        if robust_by_clean.get(clean_id, set()) != {"filler_noise", "long_context", "repetition"}
    ]
    if missing_robust:
        errors.append(f"clean samples without exactly three robust variants: {len(missing_robust)}")

    exact_duplicate_rows = sum(count for count in exact_queries.values() if count > 1)
    normalized_duplicate_rows = sum(count for count in normalized_queries.values() if count > 1)
    if exact_duplicate_rows:
        warnings.append(f"exact duplicate query rows: {exact_duplicate_rows}")
    if normalized_duplicate_rows:
        warnings.append(f"normalized duplicate query rows: {normalized_duplicate_rows}")

    return {
        "files": files,
        "total": total,
        "audit_passed": audit_passed,
        "clean_with_three_robust": len(missing_robust) == 0,
        "dev_test_leakage_count": len(leakage),
        "missing_field_record_count": missing_field_count,
        "high_critical_empty_unsafe_actions": high_critical_empty_unsafe,
        "scenario_family_distribution": dict(sorted(scenario_counts.items())),
        "risk_level_distribution": dict(sorted(risk_counts.items())),
        "exact_duplicate_query_rows": exact_duplicate_rows,
        "normalized_duplicate_query_rows": normalized_duplicate_rows,
    }


def _validate_experiments(errors: list[str], warnings: list[str]) -> dict[str, Any]:
    checks: dict[str, Any] = {"clean": {}, "robust": {}, "ablation": {}, "de_multiseed": {}}
    for suite, expected_rows in (("clean", 1000), ("robust", 3000)):
        for method in MAIN_METHODS:
            pred = FINAL_V2_DIR / suite / f"{method}_predictions.jsonl"
            summary = FINAL_V2_DIR / suite / f"{method}_summary.json"
            pred_count = count_jsonl(pred)
            summary_json = read_json(summary)
            checks[suite][method] = {
                "predictions": {**_file_record(pred), "samples": pred_count, "expected": expected_rows},
                "summary": _file_record(summary),
            }
            if not pred.exists():
                errors.append(f"{suite} prediction missing: {method}")
            elif pred_count != expected_rows:
                errors.append(f"{suite} prediction count mismatch: {method} expected {expected_rows}, got {pred_count}")
            if not summary.exists():
                errors.append(f"{suite} summary missing: {method}")
            elif int(summary_json.get("num_predictions", -1)) != expected_rows:
                warnings.append(f"{suite} summary num_predictions differs from expected for {method}")

    for ablation in ABLATIONS:
        pred = FINAL_V2_DIR / "ablation" / f"{ablation}_predictions.jsonl"
        summary = FINAL_V2_DIR / "ablation" / f"{ablation}_summary.json"
        pred_count = count_jsonl(pred)
        checks["ablation"][ablation] = {
            "predictions": {**_file_record(pred), "samples": pred_count, "expected": 3000},
            "summary": _file_record(summary),
        }
        if not pred.exists():
            errors.append(f"ablation prediction missing: {ablation}")
        elif pred_count != 3000:
            errors.append(f"ablation prediction count mismatch: {ablation} expected 3000, got {pred_count}")
        if not summary.exists():
            errors.append(f"ablation summary missing: {ablation}")

    for seed in (7, 21, 42, 2024, 2026):
        seed_dir = FINAL_V2_DIR / "de_multiseed" / f"seed_{seed}"
        files = {
            "policy": seed_dir / f"policy_de_seed_{seed}.json",
            "metrics": seed_dir / "de_best_metrics.json",
            "curve": seed_dir / "de_curve.csv",
            "trials": seed_dir / "de_trials.csv",
        }
        checks["de_multiseed"][f"seed_{seed}"] = {name: _file_record(path) for name, path in files.items()}
        missing = [name for name, path in files.items() if not path.exists()]
        if missing:
            warnings.append(f"DE multiseed seed_{seed} missing: {', '.join(missing)}")

    manifest = FINAL_V2_DIR / "final_run_manifest.json"
    if not manifest.exists():
        errors.append("final_run_manifest.json missing")
    checks["final_run_manifest"] = _file_record(manifest)
    return checks


def _validate_statistics(errors: list[str], warnings: list[str]) -> dict[str, Any]:
    required = {
        "final_metrics_by_method.csv": FINAL_V2_DIR / "statistics" / "final_metrics_by_method.csv",
        "perturbation_metrics.csv": FINAL_V2_DIR / "statistics" / "perturbation_metrics.csv",
        "ablation_metrics.csv": FINAL_V2_DIR / "statistics" / "ablation_metrics.csv",
        "bootstrap_ci.csv": FINAL_V2_DIR / "statistics" / "bootstrap_ci.csv",
        "paper_tables_all.md": FINAL_V2_DIR / "tables" / "paper_tables_all.md",
        "selected_cases.md": FINAL_V2_DIR / "cases" / "selected_cases.md",
        "paper_evidence_manifest.json": FINAL_V2_DIR / "paper_evidence_manifest.json",
    }
    records = {name: _file_record(path) for name, path in required.items()}
    for name, path in required.items():
        if not path.exists():
            errors.append(f"statistics/table artifact missing: {name}")
    table_records: dict[str, Any] = {}
    for number in range(11, 19):
        matches = sorted((FINAL_V2_DIR / "tables").glob(f"table{number}_*.md"))
        table_records[f"table{number}"] = [_file_record(path) for path in matches]
        if not matches:
            errors.append(f"paper table {number} markdown missing")
    warning_path = FINAL_V2_DIR / "statistics" / "statistics_warnings.md"
    if warning_path.exists():
        for line in warning_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- ") and line.strip() != "- None":
                warnings.append(f"statistics: {line[2:]}")
    return {"required": records, "tables_11_to_18": table_records}


def _validate_review(errors: list[str], warnings: list[str]) -> dict[str, Any]:
    sample_path = FINAL_V2_DIR / "human_review" / "review_sample_balanced_300.jsonl"
    a_path = FINAL_V2_DIR / "human_review" / "annotator_A_labels_balanced_300.jsonl"
    b_path = FINAL_V2_DIR / "human_review" / "annotator_B_labels_balanced_300.jsonl"
    c_path = FINAL_V2_DIR / "human_review" / "final_labels_C_balanced_300.jsonl"
    report_path = FINAL_V2_DIR / "human_review" / "disagreement_report_balanced_300.json"
    report_md_path = FINAL_V2_DIR / "human_review" / "disagreement_report_balanced_300.md"
    readme_path = FINAL_V2_DIR / "human_review" / "README.md"

    files = {
        "sample": _file_record(sample_path),
        "annotator_A": _file_record(a_path),
        "annotator_B": _file_record(b_path),
        "final_C": _file_record(c_path),
        "report_json": _file_record(report_path),
        "report_md": _file_record(report_md_path),
        "README": _file_record(readme_path),
    }
    for label, path in {
        "review sample": sample_path,
        "annotator A labels": a_path,
        "annotator B labels": b_path,
        "final C labels": c_path,
        "balanced disagreement report md": report_md_path,
    }.items():
        if not path.exists():
            errors.append(f"human review artifact missing: {label}")

    sample_rows = read_jsonl(sample_path)
    method_counts = Counter(str(row.get("method") or "") for row in sample_rows)
    perturb_counts = Counter(str(row.get("perturbation_type") or "") for row in sample_rows)
    risk_counts = Counter(str(row.get("risk_level") or "") for row in sample_rows)
    if len(sample_rows) != 300:
        errors.append(f"balanced review sample count mismatch: expected 300, got {len(sample_rows)}")
    if dict(method_counts) != EXPECTED_METHOD_REVIEW:
        errors.append(f"balanced review method distribution mismatch: {dict(method_counts)}")
    if dict(perturb_counts) != EXPECTED_PERTURBATION:
        errors.append(f"balanced review perturbation distribution mismatch: {dict(perturb_counts)}")

    for label, path in (("A labels", a_path), ("B labels", b_path), ("C labels", c_path)):
        count = count_jsonl(path)
        if count != 300:
            errors.append(f"{label} count mismatch: expected 300, got {count}")

    report = read_json(report_path)
    if report:
        completion = report.get("completion", {})
        for key in ("annotator_A_completed_expected_batch", "annotator_B_completed_expected_batch", "A_B_same_case_method_batch"):
            if completion.get(key) is not True:
                errors.append(f"balanced report completion check failed: {key}")
        if completion.get("final_C_count") != 300:
            errors.append("balanced report final_C_count is not 300")
        if report.get("warnings"):
            warnings.extend(f"human_review: {warning}" for warning in report["warnings"])
    else:
        warnings.append("balanced disagreement JSON missing; used file/count checks only")

    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8").lower()
        if "not expert" not in readme and "不是专家" not in readme and "不作为真实" not in readme:
            warnings.append("human_review README may not clearly state that digital review is not expert evaluation")

    return {
        "files": files,
        "sample_count": len(sample_rows),
        "method_distribution": dict(sorted(method_counts.items())),
        "perturbation_distribution": dict(sorted(perturb_counts.items())),
        "risk_level_distribution": dict(sorted(risk_counts.items())),
        "report_completion": report.get("completion", {}) if report else {},
    }


def _write_markdown(report: dict[str, Any]) -> None:
    path = FINAL_V2_DIR / "final_v2_validation_report.md"
    status = "PASS" if report["passed"] else "FAIL"
    lines = [
        "# final_v2 Evidence Validation Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Status: {status}",
        f"- Error count: {len(report['errors'])}",
        f"- Warning count: {len(report['warnings'])}",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {item}" for item in report["errors"]] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in report["warnings"]] or ["- None"])
    lines.extend(
        [
            "",
            "## Dataset",
            "",
            f"- Total samples: {report['dataset']['total']}",
            f"- Audit passed: {report['dataset']['audit_passed']}",
            f"- dev/test leakage count: {report['dataset']['dev_test_leakage_count']}",
            f"- Missing field records: {report['dataset']['missing_field_record_count']}",
            f"- Clean samples have three robust variants: {report['dataset']['clean_with_three_robust']}",
            f"- Risk distribution: {json.dumps(report['dataset']['risk_level_distribution'], ensure_ascii=False, sort_keys=True)}",
            f"- Scenario distribution: {json.dumps(report['dataset']['scenario_family_distribution'], ensure_ascii=False, sort_keys=True)}",
            "",
            "## Human Review",
            "",
            f"- Balanced sample count: {report['human_review']['sample_count']}",
            f"- Method distribution: {json.dumps(report['human_review']['method_distribution'], ensure_ascii=False, sort_keys=True)}",
            f"- Perturbation distribution: {json.dumps(report['human_review']['perturbation_distribution'], ensure_ascii=False, sort_keys=True)}",
            f"- Risk distribution: {json.dumps(report['human_review']['risk_level_distribution'], ensure_ascii=False, sort_keys=True)}",
            "",
            "## Paper Fill Readiness",
            "",
            f"- Chapter 4 can be filled from final_v2: {report['paper_chapter4_ready']}",
            "- Source directory: `build/eval/final_v2/`",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def validate() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    file_checks: list[dict[str, Any]] = []

    for label, path in {
        "dataset_audit.md": DATA_V2_DIR / "dataset_audit.md",
        "dataset_card.md": DATA_V2_DIR / "dataset_card.md",
        "paper_evidence_manifest.json": FINAL_V2_DIR / "paper_evidence_manifest.json",
    }.items():
        _add_file_check(file_checks, errors, path, label)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": _validate_dataset(errors, warnings),
        "experiments": _validate_experiments(errors, warnings),
        "statistics_and_tables": _validate_statistics(errors, warnings),
        "human_review": _validate_review(errors, warnings),
        "required_file_checks": file_checks,
        "errors": errors,
        "warnings": warnings,
    }
    report["passed"] = len(errors) == 0
    report["paper_chapter4_ready"] = report["passed"] and len(warnings) == 0
    write_json(FINAL_V2_DIR / "final_v2_validation_report.json", report)
    _write_markdown(report)
    return report


def main() -> int:
    report = validate()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
