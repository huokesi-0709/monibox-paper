from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from benchmarks.rair_rag.scripts.jsonl_to_annotation_csv import (
    convert_jsonl_to_csv,
)


def test_convert_jsonl_to_annotation_csv(tmp_path: Path) -> None:
    input_path = tmp_path / "candidates.jsonl"
    out_path = tmp_path / "annotation.csv"
    row = {
        "id": "neg_0001",
        "raw_input": "我腿疼，但是没流血",
        "canonical_input": "我腿疼，但是没流血",
        "perturbation_types": ["negation_conflict"],
        "risk_mentions": ["pain", "bleeding"],
        "positive_risks": ["trauma_or_fracture"],
        "negated_risks": ["severe_bleeding_or_shock"],
        "operational_constraints": [],
        "primary_intent": "trauma_or_fracture",
        "secondary_intents": [],
        "expected_route": "route_trauma_or_fracture",
        "expected_protocol_id": "prot_injury_fracture",
        "should_not_trigger": ["prot_bleeding_control"],
        "risk_level": "medium",
        "guideline_refs": [{"source_id": "WHO_BEC_2018"}],
    }
    input_path.write_text(
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    count = convert_jsonl_to_csv(input_path, out_path, overwrite=False)

    assert count == 1
    with out_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["perturbation_types"] == "negation_conflict"
    assert rows[0]["risk_mentions"] == "pain|bleeding"
    assert rows[0]["should_not_trigger"] == "prot_bleeding_control"
    assert rows[0]["human_accept"] == ""
    assert rows[0]["annotator_primary_intent"] == ""

    with pytest.raises(FileExistsError):
        convert_jsonl_to_csv(input_path, out_path, overwrite=False)

