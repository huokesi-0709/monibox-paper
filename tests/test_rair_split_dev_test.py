from __future__ import annotations

import json
from pathlib import Path

from benchmarks.rair_rag.routing_schema import load_routing_cases
from benchmarks.rair_rag.scripts.split_dev_test import split_dev_test


def test_split_dev_test_keeps_canonical_groups_together(tmp_path: Path) -> None:
    gold = tmp_path / "rair_gold_all.jsonl"
    dev_out = tmp_path / "dev" / "rair_dev.jsonl"
    test_out = tmp_path / "test" / "rair_test.jsonl"
    test_negation_out = tmp_path / "test" / "rair_test_negation.jsonl"
    test_multi_out = tmp_path / "test" / "rair_test_multi_intent.jsonl"
    manifest = tmp_path / "split_manifest.json"

    write_jsonl(
        gold,
        [
            case("a1", "group_a", "negation_conflict", "trauma_or_fracture"),
            case("a2", "group_a", "multi_intent", "trauma_or_fracture"),
            case("b1", "group_b", "clean_control", "respiratory_distress"),
            case("c1", "group_c", "multi_intent", "psychological_distress"),
            case("d1", "group_d", "negation_conflict", "hypothermia"),
            case("e1", "group_e", "out_of_scope", "out_of_scope"),
        ],
    )

    summary = split_dev_test(
        input_path=gold,
        dev_out=dev_out,
        test_out=test_out,
        test_negation_out=test_negation_out,
        test_multi_out=test_multi_out,
        manifest_path=manifest,
        dev_ratio=0.4,
        test_ratio=0.6,
        seed=7,
        overwrite=False,
    )

    dev_cases = load_routing_cases(dev_out)
    test_cases = load_routing_cases(test_out)
    dev_canonical_ids = {item.canonical_id for item in dev_cases}
    test_canonical_ids = {item.canonical_id for item in test_cases}
    assert not dev_canonical_ids & test_canonical_ids
    assert summary["dev_cases"] + summary["test_cases"] == 6

    all_a_cases = [
        item
        for item in [*dev_cases, *test_cases]
        if item.canonical_id == "group_a"
    ]
    assert len(all_a_cases) == 2
    assert {item.id for item in all_a_cases} == {"a1", "a2"}
    assert {"a1", "a2"} <= {item.id for item in dev_cases} or {
        "a1",
        "a2",
    } <= {item.id for item in test_cases}

    negation_cases = load_routing_cases(test_negation_out)
    multi_cases = load_routing_cases(test_multi_out)
    assert all("negation_conflict" in item.perturbation_types for item in negation_cases)
    assert all("multi_intent" in item.perturbation_types for item in multi_cases)

    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["usage_note"].startswith("DE")
    assert manifest_data["splits"]["dev"]["num_cases"] == len(dev_cases)
    assert manifest_data["splits"]["test"]["num_cases"] == len(test_cases)
    assert "primary_intent" in manifest_data["splits"]["test"]["label_distribution"]


def case(
    item_id: str, canonical_id: str, perturbation_type: str, primary_intent: str
) -> dict[str, object]:
    return {
        "id": item_id,
        "canonical_id": canonical_id,
        "raw_input": f"sample {item_id}",
        "canonical_input": f"sample {item_id}",
        "language": "zh-CN",
        "source_type": "template_generated",
        "guideline_refs": [],
        "perturbation_types": [perturbation_type],
        "risk_mentions": [],
        "positive_risks": []
        if primary_intent == "out_of_scope"
        else [primary_intent],
        "negated_risks": [],
        "primary_intent": primary_intent,
        "secondary_intents": [],
        "operational_constraints": [],
        "expected_route": f"route_{primary_intent}",
        "expected_protocol_id": None,
        "should_not_trigger": [],
        "risk_level": "low" if primary_intent == "out_of_scope" else "medium",
        "expected_tags": [primary_intent],
        "safety_note": None,
        "reference_reply": None,
        "label_status": "consensus",
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
