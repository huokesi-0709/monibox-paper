from __future__ import annotations

import csv
import json
from pathlib import Path

from benchmarks.rair_rag.scripts.build_adjudication_sheet import (
    FIELDNAMES,
    build_adjudication_sheet,
)


def test_build_adjudication_sheet_uses_disagreement_ids(tmp_path: Path) -> None:
    base = tmp_path / "round1_merged.csv"
    ann_a = tmp_path / "round1_annotator_A.csv"
    ann_b = tmp_path / "round1_annotator_B.csv"
    metrics = tmp_path / "agreement_metrics.json"
    out = tmp_path / "adjudication_sheet.csv"

    write_rows(
        base,
        [
            {
                "id": "x1",
                "raw_input": "sample leg pain no bleeding",
                "canonical_input": "sample leg pain no bleeding",
                "perturbation_types": "negation_conflict",
                "positive_risks": "trauma_or_fracture",
                "negated_risks": "severe_bleeding_or_shock",
                "primary_intent": "trauma_or_fracture",
                "expected_route": "route_trauma_or_fracture",
                "expected_protocol_id": "prot_injury_fracture",
                "should_not_trigger": "prot_bleeding_control",
                "risk_level": "medium",
                "human_accept": "yes",
                "human_notes": "natural",
            },
            {
                "id": "x2",
                "raw_input": "sample thirsty",
                "primary_intent": "dehydration_or_resource_deprivation",
            },
        ],
    )
    write_rows(
        ann_a,
        [
            {
                "id": "x1",
                "human_accept": "yes",
                "annotator_primary_intent": "trauma_or_fracture",
                "annotator_secondary_intents": "",
                "annotator_negated_risks": "severe_bleeding_or_shock",
                "annotator_operational_constraints": "",
                "annotator_should_not_trigger": "prot_bleeding_control",
                "annotator_notes": "A ok",
            },
            {"id": "x2", "human_accept": "yes"},
        ],
    )
    write_rows(
        ann_b,
        [
            {
                "id": "x1",
                "human_accept": "needs_adjudication",
                "annotator_primary_intent": "trauma_or_fracture",
                "annotator_secondary_intents": "psychological_distress",
                "annotator_negated_risks": "severe_bleeding_or_shock",
                "annotator_operational_constraints": "",
                "annotator_should_not_trigger": "prot_bleeding_control",
                "annotator_notes": "B asks review",
            },
            {"id": "x2", "human_accept": "yes"},
        ],
    )
    metrics.write_text(
        json.dumps({"all_disagreement_ids": ["x1"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    count = build_adjudication_sheet(
        base_path=base,
        ann_a_path=ann_a,
        ann_b_path=ann_b,
        metrics_path=metrics,
        out_path=out,
        overwrite=False,
    )

    assert count == 1
    rows = read_rows(out)
    assert rows[0]["id"] == "x1"
    assert rows[0]["raw_input"] == "sample leg pain no bleeding"
    assert rows[0]["template_primary_intent"] == "trauma_or_fracture"
    assert rows[0]["annotator_a_human_accept"] == "yes"
    assert rows[0]["annotator_b_human_accept"] == "needs_adjudication"
    assert rows[0]["disagreement_fields"] == "human_accept|secondary_intents"
    assert rows[0]["final_primary_intent"] == ""
    assert rows[0]["final_notes"] == ""
    assert list(rows[0]) == FIELDNAMES


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
