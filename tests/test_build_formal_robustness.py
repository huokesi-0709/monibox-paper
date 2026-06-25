from __future__ import annotations

import json

from benchmarks.build_formal_robustness import generate_formal_robustness


def test_generate_formal_robustness_writes_three_variants_per_clean(tmp_path):
    clean = tmp_path / "clean.jsonl"
    clean.write_text(
        json.dumps(
            {
                "id": "clean_0001",
                "query": "我的腿在流血。",
                "clean_query": "我的腿在流血。",
                "perturbation_type": "clean",
                "risk_level": "high",
                "expected_route": "severe_bleeding",
                "expected_protocol_id": "prot_bleeding_control",
                "expected_primary_intent": "severe_bleeding",
                "expected_tags": ["出血"],
                "gold_chunk_ids": [],
                "unsafe_actions": ["止血带"],
                "reference_reply": "按压伤口。",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "robust.jsonl"

    count = generate_formal_robustness(clean, out)

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert count == 3
    assert {row["perturbation_type"] for row in rows} == {
        "filler_noise",
        "long_context",
        "repetition",
    }
    assert all(row["clean_id"] == "clean_0001" for row in rows)
