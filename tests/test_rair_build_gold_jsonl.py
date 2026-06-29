from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from benchmarks.rair_rag.routing_schema import load_routing_cases
from benchmarks.rair_rag.scripts.build_gold_jsonl import build_gold_jsonl


def test_build_gold_jsonl_merges_consensus_and_adjudicated(
    tmp_path: Path,
) -> None:
    candidates = tmp_path / "rair_candidates.jsonl"
    ann_a = tmp_path / "round1_annotator_A.csv"
    ann_b = tmp_path / "round1_annotator_B.csv"
    adjudication = tmp_path / "adjudication_sheet.csv"
    metrics = tmp_path / "agreement_metrics.json"
    out = tmp_path / "rair_gold_all.jsonl"
    distribution = tmp_path / "label_distribution.json"

    write_jsonl(
        candidates,
        [
            candidate("x1", "sample leg pain no bleeding", "negation_conflict"),
            candidate("x2", "sample respiratory and panic", "multi_intent"),
            candidate("x3", "sample rewrite queue", "clean_control"),
            candidate("x4", "sample adjudicated rewrite", "multi_intent"),
        ],
    )
    annotation_fields = [
        "id",
        "human_accept",
        "annotator_primary_intent",
        "annotator_secondary_intents",
        "annotator_negated_risks",
        "annotator_operational_constraints",
        "annotator_should_not_trigger",
    ]
    write_rows(
        ann_a,
        annotation_fields,
        [
            consensus_row("x1"),
            {
                **consensus_row("x2"),
                "annotator_secondary_intents": "psychological_distress",
            },
            {**consensus_row("x3"), "human_accept": "rewrite"},
            {
                **consensus_row("x4"),
                "annotator_primary_intent": "respiratory_distress",
            },
        ],
    )
    write_rows(
        ann_b,
        annotation_fields,
        [
            consensus_row("x1"),
            {
                **consensus_row("x2"),
                "human_accept": "needs_adjudication",
                "annotator_secondary_intents": "",
            },
            {**consensus_row("x3"), "human_accept": "rewrite"},
            {
                **consensus_row("x4"),
                "human_accept": "needs_adjudication",
                "annotator_primary_intent": "psychological_distress",
            },
        ],
    )
    write_rows(
        adjudication,
        [
            "id",
            "final_human_accept",
            "final_primary_intent",
            "final_secondary_intents",
            "final_negated_risks",
            "final_operational_constraints",
            "final_should_not_trigger",
            "final_expected_route",
            "final_expected_protocol_id",
            "final_risk_level",
            "final_raw_input",
            "final_notes",
        ],
        [
            {
                "id": "x2",
                "final_human_accept": "yes",
                "final_primary_intent": "respiratory_distress",
                "final_secondary_intents": "psychological_distress",
                "final_expected_route": "route_respiratory_distress",
                "final_expected_protocol_id": "prot_respiratory_distress",
                "final_risk_level": "critical",
                "final_notes": "adjudicated by codebook",
            },
            {
                "id": "x4",
                "final_human_accept": "rewrite",
                "final_primary_intent": "respiratory_distress",
                "final_notes": "needs natural rewrite before gold",
            }
        ],
    )
    metrics.write_text(
        json.dumps({"all_disagreement_ids": ["x2", "x4"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = build_gold_jsonl(
        candidates_path=candidates,
        adjudication_path=adjudication,
        ann_a_path=ann_a,
        ann_b_path=ann_b,
        metrics_path=metrics,
        out_path=out,
        distribution_path=distribution,
        overwrite=False,
    )

    assert summary == {
        "gold_cases": 2,
        "consensus_cases": 1,
        "adjudicated_cases": 1,
        "skipped_consensus_cases": 1,
        "skipped_adjudicated_cases": 1,
    }
    cases = load_routing_cases(out)
    assert [case.id for case in cases] == ["x1", "x2"]
    assert cases[0].label_status == "consensus"
    assert cases[0].negated_risks == ["severe_bleeding_or_shock"]
    assert cases[1].label_status == "adjudicated"
    assert cases[1].secondary_intents == ["psychological_distress"]
    assert cases[1].risk_level == "critical"

    dist = json.loads(distribution.read_text(encoding="utf-8"))
    assert dist["num_cases"] == 2
    assert dist["label_status"] == {"adjudicated": 1, "consensus": 1}
    assert dist["perturbation_type"] == {"multi_intent": 1, "negation_conflict": 1}


def test_build_gold_jsonl_requires_adjudicated_final_label(tmp_path: Path) -> None:
    candidates = tmp_path / "rair_candidates.jsonl"
    ann_a = tmp_path / "round1_annotator_A.csv"
    ann_b = tmp_path / "round1_annotator_B.csv"
    adjudication = tmp_path / "adjudication_sheet.csv"
    metrics = tmp_path / "agreement_metrics.json"

    write_jsonl(candidates, [candidate("x1", "sample", "multi_intent")])
    write_rows(
        ann_a,
        ["id", "human_accept", "annotator_primary_intent"],
        [{"id": "x1", "human_accept": "yes", "annotator_primary_intent": "x"}],
    )
    write_rows(
        ann_b,
        ["id", "human_accept", "annotator_primary_intent"],
        [
            {
                "id": "x1",
                "human_accept": "needs_adjudication",
                "annotator_primary_intent": "y",
            }
        ],
    )
    write_rows(
        adjudication,
        ["id", "final_human_accept", "final_primary_intent"],
        [{"id": "x1", "final_human_accept": "yes", "final_primary_intent": ""}],
    )
    metrics.write_text(
        json.dumps({"all_disagreement_ids": ["x1"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="final_primary_intent"):
        build_gold_jsonl(
            candidates_path=candidates,
            adjudication_path=adjudication,
            ann_a_path=ann_a,
            ann_b_path=ann_b,
            metrics_path=metrics,
            out_path=tmp_path / "gold.jsonl",
            distribution_path=tmp_path / "dist.json",
            overwrite=False,
        )


def candidate(item_id: str, raw_input: str, perturbation_type: str) -> dict[str, object]:
    return {
        "id": item_id,
        "canonical_id": f"case_{item_id}",
        "raw_input": raw_input,
        "canonical_input": raw_input,
        "language": "zh-CN",
        "source_type": "template_generated",
        "perturbation_types": [perturbation_type],
        "positive_risks": ["trauma_or_fracture"],
        "negated_risks": [],
        "operational_constraints": [],
        "primary_intent": "trauma_or_fracture",
        "secondary_intents": [],
        "should_not_trigger": [],
        "expected_route": "route_trauma_or_fracture",
        "expected_protocol_id": "prot_injury_fracture",
        "risk_level": "medium",
        "expected_tags": ["risk_injury"],
        "label_status": "candidate",
    }


def consensus_row(item_id: str) -> dict[str, str]:
    return {
        "id": item_id,
        "human_accept": "yes",
        "annotator_primary_intent": "trauma_or_fracture",
        "annotator_secondary_intents": "",
        "annotator_negated_risks": "severe_bleeding_or_shock",
        "annotator_operational_constraints": "",
        "annotator_should_not_trigger": "prot_bleeding_control",
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_rows(
    path: Path, fieldnames: list[str], rows: list[dict[str, str]]
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
