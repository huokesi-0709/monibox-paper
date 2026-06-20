from __future__ import annotations

import json

from app.config import PROJECT_ROOT
from runtime.scoring import (
    compute_unsafe_score,
    load_policy,
    rerank_chunks,
    score_chunk,
)


def _chunk(**overrides):
    base = {
        "chunk_id": "chunk_safe",
        "text": "腿部流血时先直接按压伤口，保持呼吸平稳，等待救援。",
        "category": "急救",
        "sub_category": "出血",
        "dimension": "safety",
        "risk": "severe_bleeding",
        "scene": "地震 废墟",
        "tags_flat": "|出血|腿|地震|",
        "status": "启用",
        "quality_score": 5.0,
        "distance": 0.2,
        "group_id": "g1",
    }
    base.update(overrides)
    return base


def test_policy_manual_can_load():
    policy = load_policy()
    assert policy.version == "manual-v1"
    assert "w_vec" in policy.weights
    assert "min_final_score" in policy.thresholds


def test_policy_de_can_load_by_path():
    policy = load_policy("scoring/policy_de.json")
    assert policy.version == "hsc-rag-de-v1"
    assert "w_unsafe" in policy.weights


def test_search_space_weights_align_with_policy_weights():
    policy = load_policy()
    search_space = json.loads(
        (PROJECT_ROOT / "scoring" / "search_space.json").read_text(encoding="utf-8")
    )
    assert set(search_space["weights"]) == set(policy.weights)


def test_unsafe_chunk_is_penalized():
    safe = _chunk(chunk_id="safe")
    unsafe = _chunk(chunk_id="unsafe", text="流血时可以使用止血带，并给出药物剂量。")

    safe_score = score_chunk("我的腿在流血", safe).final_score
    unsafe_score = score_chunk("我的腿在流血", unsafe).final_score

    assert compute_unsafe_score(unsafe) > 0
    assert unsafe_score < safe_score


def test_tag_and_risk_match_raise_relevant_chunk_score():
    relevant = _chunk(chunk_id="bleeding")
    unrelated = _chunk(
        chunk_id="battery",
        text="手机快没电时降低亮度，关闭不必要应用。",
        risk="low_battery",
        scene="通信",
        tags_flat="|手机|电量|",
        distance=0.2,
    )

    relevant_score = score_chunk(
        "我的腿在流血",
        relevant,
        routed_tags=["腿", "出血"],
    ).final_score
    unrelated_score = score_chunk(
        "我的腿在流血",
        unrelated,
        routed_tags=["腿", "出血"],
    ).final_score

    assert relevant_score > unrelated_score


def test_distance_smaller_gives_higher_vector_similarity():
    near = score_chunk("我的腿在流血", _chunk(distance=0.1))
    far = score_chunk("我的腿在流血", _chunk(distance=0.9))

    assert near.sim_vec > far.sim_vec


def test_rerank_outputs_explanation_and_breakdown():
    chunks = [
        _chunk(chunk_id="battery", text="手机没电时节省电量。", risk="low_battery"),
        _chunk(chunk_id="bleeding"),
    ]

    ranked = rerank_chunks(
        "我的腿在流血",
        chunks,
        routed_tags=["腿", "出血"],
        topk=2,
    )

    assert ranked[0]["chunk_id"] == "bleeding"
    assert ranked[0]["score_breakdown"]["explanation"]
    assert "final_score" in ranked[0]["score_breakdown"]
