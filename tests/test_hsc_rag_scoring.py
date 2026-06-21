from __future__ import annotations

import json
from typing import Any

from runtime.intent_extractor import IntentExtractor
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.protocol_matcher import ProtocolMatchResult
from runtime.rag_engine import SearchResult
from runtime.scoring import (
    HscRagPolicy,
    compute_unsafe_score,
    load_policy,
    rerank_chunks,
    score_chunk,
)


def _chunk(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chunk_id": "safe_bleeding",
        "text": "腿部流血或出血时，先直接按压伤口，减少活动，等待救援。",
        "category": "急救",
        "sub_category": "出血",
        "dimension": "safety",
        "risk": "severe_bleeding",
        "scene": "地震 废墟",
        "tags_flat": "|risk_bleeding|body:腿|scene:地震|流血|止血|",
        "status": "启用",
        "quality_score": 5.0,
        "distance": 0.25,
        "group_id": "g_bleeding",
    }
    base.update(overrides)
    return base


def _intent(text: str):
    return IntentExtractor().extract(text)


def _vector_only_policy() -> HscRagPolicy:
    return HscRagPolicy(
        weights={
            "w_vec": 1.0,
            "w_sparse": 0.0,
            "w_quality": 0.0,
            "w_tag": 0.0,
            "w_risk": 0.0,
            "w_unsafe": 0.0,
            "w_redundancy": 0.0,
        },
        thresholds={},
        version="vector-only-test",
    )


class _Route:
    def __init__(self) -> None:
        self.tags = ["risk_bleeding", "body:腿"]
        self.cross_dimension = False
        self.dimension = "safety"


class _Router:
    def route(self, text: str, top_tags: int = 2) -> _Route:
        del text, top_tags
        return _Route()


class _FakeRag:
    router = _Router()

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def is_vague_query(self, text: str) -> bool:
        del text
        return False

    def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        self.calls.append({"query": query, **kwargs})
        return [
            SearchResult(
                chunk_id="rag_1",
                display_id=None,
                group_id="g1",
                text="腿部流血时先直接按压伤口。",
                category="急救",
                sub_category="出血",
                dimension="safety",
                risk="severe_bleeding",
                scene="地震",
                source_id="test",
                status="启用",
                quality_score=5.0,
                priority=1,
                hardware_action_hint=None,
                distance=0.1,
                final_distance=0.1,
                tags_flat="|risk_bleeding|body:腿|",
                score_breakdown={"final_score": 0.9},
            )
        ]


class _FakeProtocol:
    def match_with_score(
        self,
        text: str,
        routed_tags: list[str],
        events: list[str],
        intent_context=None,
    ) -> ProtocolMatchResult:
        del text, routed_tags, events, intent_context
        return ProtocolMatchResult(
            matched=False,
            protocol_id=None,
            protocol_name=None,
            confidence=0.0,
            priority=0,
            matched_terms=[],
            body_part_matches=[],
            scene_matches=[],
            negation_conflict=False,
            reason=["test no protocol"],
            protocol=None,
        )


class _FakeOutput:
    last_guard_result = None
    last_output_result = None

    def set_turn_context(self, context: dict) -> None:
        del context

    def emit(self, text: str, **kwargs: Any) -> str:
        del kwargs
        return text


class _FakeLLM:
    @property
    def backend_name(self) -> str:
        return "null"

    def generate(self, *args: Any, **kwargs: Any) -> str:
        del args, kwargs
        return ""

    def stream_generate(self, *args: Any, **kwargs: Any):
        del args, kwargs
        return
        yield


class _FakeRagGenerator:
    def generate(self, query: str, results: list[SearchResult], high_risk: bool, mem):
        del results, high_risk, mem
        return f"rag reply for {query}"


def test_policy_loading_and_missing_policy_fallback():
    manual = load_policy("scoring/policy_manual.json")
    de = load_policy("scoring/policy_de.json")
    missing = load_policy("scoring/does_not_exist_policy.json")

    assert manual.version == "manual-v1"
    assert de.version == "hsc-rag-de-v1"
    assert missing.version == "manual-v1"
    assert "w_vec" in missing.weights


def test_unsafe_penalty_lowers_final_score():
    safe = _chunk(chunk_id="safe")
    unsafe = _chunk(
        chunk_id="unsafe",
        text="流血时可以使用止血带，必要时自行注射并给出药物剂量，保证获救。",
    )

    safe_score = score_chunk("我的腿在流血", safe).final_score
    unsafe_breakdown = score_chunk("我的腿在流血", unsafe)

    assert compute_unsafe_score(unsafe) > 0
    assert unsafe_breakdown.unsafe > 0
    assert unsafe_breakdown.final_score < safe_score


def test_risk_match_uses_severe_bleeding_intent_context():
    ctx = _intent("我的腿在流血")
    bleeding = _chunk(chunk_id="bleeding")
    unrelated = _chunk(
        chunk_id="battery",
        text="手机快没电时降低亮度。",
        risk="low_battery",
        tags_flat="|risk_low_battery|",
    )

    assert score_chunk("我的腿在流血", bleeding, intent_context=ctx).risk_match > (
        score_chunk("我的腿在流血", unrelated, intent_context=ctx).risk_match
    )


def test_risk_match_covers_respiratory_and_trapped_contexts():
    respiratory_ctx = _intent("我喘不上气")
    trapped_ctx = _intent("我被困在废墟里，腿被压住")
    respiratory = _chunk(
        chunk_id="breath",
        text="呼吸困难或喘不上气时保持半坐位，缓慢呼吸。",
        risk="respiratory_distress",
        tags_flat="|risk_respiratory|",
    )
    trapped = _chunk(
        chunk_id="trapped",
        text="被困或压住时不要强行拉出，保存体力等待救援。",
        risk="trapped_or_crush",
        tags_flat="|risk_trapped|scene:废墟|",
    )

    assert score_chunk("我喘不上气", respiratory, intent_context=respiratory_ctx).risk_match > 0
    assert score_chunk("我被困在废墟里", trapped, intent_context=trapped_ctx).risk_match > 0


def test_tag_body_scene_match_uses_intent_context():
    ctx = {
        "primary_intent": "severe_bleeding",
        "secondary_intents": [],
        "body_parts": ["腿"],
        "scene_terms": ["地震"],
        "tags": ["risk_bleeding", "body:腿", "scene:地震"],
    }
    relevant = _chunk()

    breakdown = score_chunk(
        "我的腿在流血",
        relevant,
        routed_tags=["risk_bleeding"],
        intent_context=ctx,
    )

    assert breakdown.tag_match > 0


def test_redundancy_penalty_lowers_duplicate_chunk_score():
    first = _chunk(chunk_id="first", text="腿部流血时先直接按压伤口。")
    duplicate = _chunk(chunk_id="duplicate", text="腿部流血时先直接按压伤口。")

    without_redundancy = score_chunk("我的腿在流血", duplicate)
    with_redundancy = score_chunk(
        "我的腿在流血", duplicate, selected_chunks=[first]
    )

    assert with_redundancy.redundancy > 0
    assert with_redundancy.final_score < without_redundancy.final_score


def test_rerank_order_prefers_safe_relevant_chunk_over_unsafe_vector_hit():
    unsafe_vector_hit = _chunk(
        chunk_id="unsafe_vector",
        text="流血时立刻使用止血带并自行注射，保证获救。",
        distance=0.01,
        quality_score=1.0,
    )
    safe_relevant = _chunk(
        chunk_id="safe_relevant",
        text="腿部流血或出血时，直接按压伤口，减少活动，等待救援。",
        distance=0.22,
        quality_score=5.0,
    )
    unrelated = _chunk(
        chunk_id="unrelated",
        text="手机快没电时关闭不必要功能。",
        risk="low_battery",
        tags_flat="|risk_low_battery|",
        distance=0.4,
    )

    ranked = rerank_chunks(
        "我的腿在流血",
        [unsafe_vector_hit, safe_relevant, unrelated],
        routed_tags=["risk_bleeding", "body:腿"],
        intent_context=_intent("我的腿在流血"),
        topk=3,
    )

    assert ranked[0]["chunk_id"] == "safe_relevant"
    assert ranked[0]["score_breakdown"]["unsafe"] == 0
    assert ranked[1]["chunk_id"] == "unsafe_vector"


def test_score_breakdown_and_final_distance_are_serializable():
    ranked = rerank_chunks(
        "我的腿在流血",
        [_chunk(chunk_id="safe"), _chunk(chunk_id="other", distance=0.5)],
        intent_context=_intent("我的腿在流血"),
        topk=2,
    )
    first = ranked[0]

    assert "score_breakdown" in first
    assert "final_distance" in first
    for key in [
        "final_score",
        "sim_vec",
        "sim_sparse",
        "quality",
        "tag_match",
        "risk_match",
        "unsafe",
        "redundancy",
        "explanation",
    ]:
        assert key in first["score_breakdown"]
    json.dumps(first["score_breakdown"], ensure_ascii=False)


def test_vector_only_policy_sorts_by_vector_similarity():
    unsafe_near = _chunk(
        chunk_id="unsafe_near",
        text="无关文本，包含止血带和保证获救。",
        distance=0.01,
        risk="low_battery",
        tags_flat="|risk_low_battery|",
    )
    safe_relevant_far = _chunk(
        chunk_id="safe_far",
        text="腿部流血时直接按压伤口。",
        distance=0.5,
    )

    ranked = rerank_chunks(
        "我的腿在流血",
        [safe_relevant_far, unsafe_near],
        policy=_vector_only_policy(),
        routed_tags=["risk_bleeding"],
        intent_context=_intent("我的腿在流血"),
        topk=2,
    )

    assert ranked[0]["chunk_id"] == "unsafe_near"
    assert ranked[0]["score_breakdown"]["unsafe"] > 0
    assert ranked[0]["score_breakdown"]["final_score"] == ranked[0]["score_breakdown"]["sim_vec"]
    assert ranked[1]["score_breakdown"]["final_score"] == ranked[1]["score_breakdown"]["sim_vec"]


def test_monibox_session_passes_intent_context_to_rag_search():
    rag = _FakeRag()
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=rag,
        protocol_engine=_FakeProtocol(),
        output_pipeline=_FakeOutput(),
        llm=_FakeLLM(),
        rag_generator=_FakeRagGenerator(),
    )

    session.handle("退在留血")

    assert rag.calls
    first_call = rag.calls[0]
    assert first_call["query"] == "腿在流血"
    assert first_call["tags"] == ["risk_bleeding", "body:腿"]
    assert first_call["intent_context"].primary_intent == "severe_bleeding"
    assert session.last_trace["canonical_text"] == "腿在流血"
    assert session.last_trace["top_chunks"][0]["score_breakdown"]["final_score"] == 0.9
