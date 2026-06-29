from __future__ import annotations

import csv
from pathlib import Path

from benchmarks.rair_rag.scripts.compute_agreement import (
    compute_agreement,
    write_markdown,
)


def test_compute_agreement_reports_disagreement_ids(tmp_path: Path) -> None:
    ann_a = tmp_path / "a.csv"
    ann_b = tmp_path / "b.csv"
    fieldnames = [
        "id",
        "perturbation_types",
        "human_accept",
        "annotator_primary_intent",
        "annotator_negated_risks",
        "annotator_secondary_intents",
        "annotator_operational_constraints",
        "annotator_should_not_trigger",
    ]
    write_rows(
        ann_a,
        fieldnames,
        [
            {
                "id": "x1",
                "perturbation_types": "negation_conflict",
                "human_accept": "yes",
                "annotator_primary_intent": "trauma_or_fracture",
                "annotator_negated_risks": "severe_bleeding_or_shock",
                "annotator_should_not_trigger": "prot_bleeding_control",
            },
            {
                "id": "x2",
                "perturbation_types": "multi_intent",
                "human_accept": "yes",
                "annotator_primary_intent": "respiratory_distress",
                "annotator_secondary_intents": "psychological_distress",
            },
        ],
    )
    write_rows(
        ann_b,
        fieldnames,
        [
            {
                "id": "x1",
                "perturbation_types": "negation_conflict",
                "human_accept": "yes",
                "annotator_primary_intent": "trauma_or_fracture",
                "annotator_negated_risks": "severe_bleeding_or_shock",
                "annotator_should_not_trigger": "prot_bleeding_control",
            },
            {
                "id": "x2",
                "perturbation_types": "multi_intent",
                "human_accept": "needs_adjudication",
                "annotator_primary_intent": "psychological_distress",
                "annotator_secondary_intents": "",
            },
        ],
    )

    report = compute_agreement(ann_a, ann_b)

    assert report["num_common_cases"] == 2
    assert report["single_label"]["primary_intent"]["num_disagreements"] == 1
    assert report["multi_label"]["negated_risks"]["exact_match"] == 1.0
    assert report["multi_label"]["secondary_intents"]["num_disagreements"] == 1
    assert report["all_disagreement_ids"] == ["x2"]

    out_md = tmp_path / "report.md"
    write_markdown(out_md, report)
    assert "- x2" in out_md.read_text(encoding="utf-8")


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

