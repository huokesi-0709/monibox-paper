from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROUND_DIR = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "annotation_rounds"
)
REPORT_DIR = PROJECT_ROOT / "benchmarks" / "rair_rag" / "reports"
DEFAULT_ANN_A = ROUND_DIR / "round1_annotator_A.csv"
DEFAULT_ANN_B = ROUND_DIR / "round1_annotator_B.csv"
DEFAULT_JSON = REPORT_DIR / "agreement_metrics.json"
DEFAULT_MD = REPORT_DIR / "agreement_report.md"

SINGLE_LABEL_FIELDS = {
    "human_accept": "human_accept",
    "primary_intent": "annotator_primary_intent",
    "perturbation_types": "perturbation_types",
}
MULTI_LABEL_FIELDS = {
    "negated_risks": "annotator_negated_risks",
    "secondary_intents": "annotator_secondary_intents",
    "operational_constraints": "annotator_operational_constraints",
    "should_not_trigger": "annotator_should_not_trigger",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute RAIR-RAG inter-annotator agreement."
    )
    parser.add_argument("--ann-a", type=Path, default=DEFAULT_ANN_A)
    parser.add_argument("--ann-b", type=Path, default=DEFAULT_ANN_B)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    report = compute_agreement(args.ann_a, args.ann_b)
    write_json(args.out_json, report)
    write_markdown(args.out_md, report)
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")


def compute_agreement(ann_a: Path, ann_b: Path) -> dict[str, Any]:
    rows_a = read_rows(ann_a)
    rows_b = read_rows(ann_b)
    ids_a = set(rows_a)
    ids_b = set(rows_b)
    common_ids = sorted(ids_a & ids_b)
    if not common_ids:
        raise ValueError("annotator files do not share any id values")

    single_label = {
        logical_name: single_label_metrics(
            [rows_a[item_id].get(column_name, "") for item_id in common_ids],
            [rows_b[item_id].get(column_name, "") for item_id in common_ids],
            common_ids,
        )
        for logical_name, column_name in SINGLE_LABEL_FIELDS.items()
    }
    multi_label = {
        logical_name: multi_label_metrics(
            [split_labels(rows_a[item_id].get(column_name, "")) for item_id in common_ids],
            [split_labels(rows_b[item_id].get(column_name, "")) for item_id in common_ids],
            common_ids,
        )
        for logical_name, column_name in MULTI_LABEL_FIELDS.items()
    }
    all_disagreement_ids = sorted(
        {
            item_id
            for metrics in [*single_label.values(), *multi_label.values()]
            for item_id in metrics["disagreement_ids"]
        }
    )
    return {
        "num_common_cases": len(common_ids),
        "missing_from_annotator_a": sorted(ids_b - ids_a),
        "missing_from_annotator_b": sorted(ids_a - ids_b),
        "single_label": single_label,
        "multi_label": multi_label,
        "all_disagreement_ids": all_disagreement_ids,
        "num_disagreement_cases": len(all_disagreement_ids),
    }


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    output: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        item_id = (row.get("id") or "").strip()
        if not item_id:
            raise ValueError(f"{path}: row {index} is missing id")
        if item_id in output:
            raise ValueError(f"{path}: duplicate id {item_id}")
        output[item_id] = {
            key: (value or "").strip() for key, value in row.items()
        }
    return output


def single_label_metrics(
    left: list[str], right: list[str], item_ids: list[str]
) -> dict[str, Any]:
    if len(left) != len(right):
        raise ValueError("single-label inputs must have the same length")
    total = len(left)
    matches = [a == b for a, b in zip(left, right, strict=True)]
    disagreement_ids = [
        item_id for item_id, matched in zip(item_ids, matches, strict=True) if not matched
    ]
    return {
        "num_cases": total,
        "observed_agreement": ratio(sum(matches), total),
        "cohen_kappa": cohen_kappa(left, right),
        "macro_f1": macro_f1(left, right),
        "disagreement_ids": disagreement_ids,
        "num_disagreements": len(disagreement_ids),
        "annotator_a_distribution": dict(sorted(Counter(left).items())),
        "annotator_b_distribution": dict(sorted(Counter(right).items())),
    }


def multi_label_metrics(
    left: list[set[str]], right: list[set[str]], item_ids: list[str]
) -> dict[str, Any]:
    if len(left) != len(right):
        raise ValueError("multi-label inputs must have the same length")
    exact_matches = [a == b for a, b in zip(left, right, strict=True)]
    disagreement_ids = [
        item_id
        for item_id, matched in zip(item_ids, exact_matches, strict=True)
        if not matched
    ]
    tp = fp = fn = 0
    for a, b in zip(left, right, strict=True):
        tp += len(a & b)
        fp += len(b - a)
        fn += len(a - b)
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    f1 = ratio(2 * precision * recall, precision + recall)
    return {
        "num_cases": len(left),
        "exact_match": ratio(sum(exact_matches), len(left)),
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": f1,
        "true_positive_labels": tp,
        "false_positive_labels": fp,
        "false_negative_labels": fn,
        "disagreement_ids": disagreement_ids,
        "num_disagreements": len(disagreement_ids),
    }


def cohen_kappa(left: list[str], right: list[str]) -> float:
    if len(left) != len(right):
        raise ValueError("kappa inputs must have the same length")
    total = len(left)
    if total == 0:
        return 0.0
    observed = ratio(sum(1 for a, b in zip(left, right, strict=True) if a == b), total)
    left_counts = Counter(left)
    right_counts = Counter(right)
    labels = set(left_counts) | set(right_counts)
    expected = sum(
        (left_counts[label] / total) * (right_counts[label] / total)
        for label in labels
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def macro_f1(gold: list[str], pred: list[str]) -> float:
    labels = sorted(set(gold) | set(pred))
    if not labels:
        return 0.0
    scores: list[float] = []
    for label in labels:
        tp = sum(1 for g, p in zip(gold, pred, strict=True) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, pred, strict=True) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, pred, strict=True) if g == label and p != label)
        precision = ratio(tp, tp + fp)
        recall = ratio(tp, tp + fn)
        scores.append(ratio(2 * precision * recall, precision + recall))
    return sum(scores) / len(scores)


def split_labels(value: str) -> set[str]:
    if not value:
        return set()
    normalized = value.replace("；", "|").replace(";", "|").replace(",", "|")
    return {item.strip() for item in normalized.split("|") if item.strip()}


def ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# RAIR-RAG Annotation Agreement Report",
        "",
        f"- Common cases: {report['num_common_cases']}",
        f"- Disagreement cases: {report['num_disagreement_cases']}",
        f"- Missing from annotator A: {len(report['missing_from_annotator_a'])}",
        f"- Missing from annotator B: {len(report['missing_from_annotator_b'])}",
        "",
        "## Single-Label Fields",
        "",
        "| Field | Observed Agreement | Cohen's Kappa | Macro-F1 | Disagreements |",
        "|---|---:|---:|---:|---:|",
    ]
    for field_name, metrics in report["single_label"].items():
        lines.append(
            "| "
            f"{field_name} | "
            f"{metrics['observed_agreement']:.4f} | "
            f"{metrics['cohen_kappa']:.4f} | "
            f"{metrics['macro_f1']:.4f} | "
            f"{metrics['num_disagreements']} |"
        )
    lines.extend(
        [
            "",
            "## Multi-Label Fields",
            "",
            "| Field | Exact Match | Micro Precision | Micro Recall | Micro-F1 | Disagreements |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for field_name, metrics in report["multi_label"].items():
        lines.append(
            "| "
            f"{field_name} | "
            f"{metrics['exact_match']:.4f} | "
            f"{metrics['micro_precision']:.4f} | "
            f"{metrics['micro_recall']:.4f} | "
            f"{metrics['micro_f1']:.4f} | "
            f"{metrics['num_disagreements']} |"
        )
    lines.extend(["", "## Disagreement IDs", ""])
    if report["all_disagreement_ids"]:
        lines.extend(f"- {item_id}" for item_id in report["all_disagreement_ids"])
    else:
        lines.append("- None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
