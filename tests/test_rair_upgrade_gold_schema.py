from __future__ import annotations

import json
from pathlib import Path

from benchmarks.rair_rag.routing_schema import load_routing_cases
from benchmarks.rair_rag.scripts.upgrade_gold_schema import upgrade_gold_schema


def test_upgrade_gold_schema_builds_structured_risk_candidates(tmp_path: Path) -> None:
    source = tmp_path / "old_gold.jsonl"
    out = tmp_path / "gold_v2.jsonl"
    warnings = tmp_path / "warnings.jsonl"
    rows = [
        {
            "id": "case1",
            "canonical_id": "case_resp",
            "raw_input": "我喘不上气",
            "canonical_input": "我喘不上气",
            "language": "zh-CN",
            "source_type": "template_generated_human_reviewed",
            "risk_mentions": ["respiratory_distress:喘不上气"],
            "positive_risks": ["respiratory_distress"],
            "negated_risks": [],
            "primary_intent": "respiratory_distress",
            "secondary_intents": [],
            "operational_constraints": [],
            "expected_route": "route_respiratory_distress",
            "expected_protocol_id": "prot_respiratory_distress",
            "should_not_trigger": [],
            "risk_level": "critical",
            "expected_tags": [],
        },
        {
            "id": "case2",
            "canonical_id": "case_boundary",
            "raw_input": "你能帮我写诗吗",
            "canonical_input": "你能帮我写诗吗",
            "language": "zh-CN",
            "source_type": "template_generated_human_reviewed",
            "risk_mentions": ["inferred:out_of_scope"],
            "positive_risks": [],
            "negated_risks": [],
            "primary_intent": "out_of_scope",
            "secondary_intents": [],
            "operational_constraints": [],
            "expected_route": "route_out_of_scope",
            "expected_protocol_id": None,
            "should_not_trigger": [],
            "risk_level": "low",
            "expected_tags": [],
        },
    ]
    write_jsonl(source, rows)

    summary = upgrade_gold_schema(source, out, warnings)

    assert summary == {
        "input_cases": 2,
        "output_cases": 2,
        "warnings": 0,
        "with_risk_candidates": 2,
    }
    upgraded = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert upgraded[0]["risk_candidates"] == [
        {
            "risk": "respiratory_distress",
            "trigger": "喘不上气",
            "span": [1, 5],
            "confidence": 0.71,
            "evidence_type": "protocol_alias",
            "expected_negated": False,
        }
    ]
    assert upgraded[1]["risk_candidates"][0]["risk"] == "out_of_scope"
    assert upgraded[1]["risk_candidates"][0]["trigger"] == "你能帮我写诗吗"
    assert upgraded[1]["risk_candidates"][0]["span"] == [0, 7]
    assert warnings.read_text(encoding="utf-8") == ""
    assert [case.id for case in load_routing_cases(out)] == ["case1", "case2"]


def test_upgrade_gold_schema_warns_for_unlocated_trigger(tmp_path: Path) -> None:
    source = tmp_path / "old_gold.jsonl"
    out = tmp_path / "gold_v2.jsonl"
    warnings = tmp_path / "warnings.jsonl"
    write_jsonl(
        source,
        [
            {
                "id": "case1",
                "canonical_id": "case_warn",
                "raw_input": "我腿疼",
                "canonical_input": "我腿疼",
                "language": "zh-CN",
                "source_type": "template_generated_human_reviewed",
                "risk_mentions": ["trauma_or_fracture:流血"],
                "positive_risks": ["trauma_or_fracture"],
                "negated_risks": [],
                "primary_intent": "trauma_or_fracture",
                "secondary_intents": [],
                "operational_constraints": [],
                "expected_route": "route_trauma_or_fracture",
                "expected_protocol_id": "prot_injury_fracture",
                "should_not_trigger": [],
                "risk_level": "medium",
                "expected_tags": [],
            }
        ],
    )

    summary = upgrade_gold_schema(source, out, warnings)

    assert summary["warnings"] == 1
    warning = json.loads(warnings.read_text(encoding="utf-8"))
    assert warning["reason"] == "trigger_not_found"
    case = load_routing_cases(out)[0]
    assert case.risk_candidates[0]["span"] == [-1, -1]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
