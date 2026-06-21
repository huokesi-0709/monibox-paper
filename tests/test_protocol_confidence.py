from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.input_normalizer import InputNormalizer
from runtime.intent_extractor import IntentExtractor
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.protocol_matcher import ProtocolEngine, ProtocolMatchResult


class _Route:
    def __init__(self) -> None:
        self.tags: list[str] = []
        self.cross_dimension = False
        self.dimension = None


class _Router:
    def route(self, text: str, top_tags: int = 2) -> _Route:
        del text, top_tags
        return _Route()


class _FakeRag:
    router = _Router()

    def is_vague_query(self, text: str) -> bool:
        del text
        return False

    def search(self, *args, **kwargs) -> list:
        del args, kwargs
        return []


class _FakeOutput:
    def set_turn_context(self, context: dict) -> None:
        del context

    def emit(self, text: str, **kwargs) -> str:
        del kwargs
        return text


class _FakeLLM:
    @property
    def backend_name(self) -> str:
        return "null"

    def generate(self, *args, **kwargs) -> str:
        del args, kwargs
        return ""

    def stream_generate(self, *args, **kwargs):
        del args, kwargs
        return
        yield


class _ProtocolSpy:
    match_called = False
    match_with_score_called = False
    seen_text = ""
    seen_intent_context: Any = None

    def match(self, text: str, routed_tags: list[str], events: list[str]):
        del text, routed_tags, events
        self.match_called = True
        raise AssertionError("MoniSession should use match_with_score()")

    def match_with_score(
        self,
        text: str,
        routed_tags: list[str],
        events: list[str],
        intent_context=None,
    ) -> ProtocolMatchResult:
        del routed_tags, events
        self.match_with_score_called = True
        self.seen_text = text
        self.seen_intent_context = intent_context
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
            reason=["spy no match"],
            protocol=None,
        )


def _intent_for(text: str):
    canonical = InputNormalizer().normalize(text).canonical_text
    return canonical, IntentExtractor().extract(canonical)


def _match(text: str, *, events: list[str] | None = None, routed_tags: list[str] | None = None):
    canonical = InputNormalizer().normalize(text).canonical_text
    intent = IntentExtractor().extract(canonical)
    return ProtocolEngine().match_with_score(
        canonical,
        routed_tags=routed_tags or [],
        events=events or [],
        intent_context=intent,
    )


def test_bleeding_protocol_confidence_is_high():
    result = _match("我的腿在流血")

    assert result.matched is True
    assert result.protocol_id == "prot_bleeding_control"
    assert result.confidence > 0.6
    assert "流血" in result.matched_terms
    assert "腿" in result.body_part_matches
    assert any("keyword" in item for item in result.reason)
    assert any("risk" in item for item in result.reason)
    assert any("body parts" in item for item in result.reason)
    assert result.score_breakdown["keyword_hit"] == 1.0
    assert result.threshold == ProtocolEngine.MATCH_THRESHOLD
    assert "severe_bleeding" in result.active_risks
    assert "severe_bleeding" in result.protocol_risks


def test_negated_bleeding_is_not_high_confidence():
    result = _match("腿疼但是没流血")

    assert not (
        result.protocol_id == "prot_bleeding_control" and result.confidence > 0.6
    )
    assert result.matched is False
    assert result.confidence < ProtocolEngine.MATCH_THRESHOLD
    assert result.negation_conflict is True
    assert "severe_bleeding" in result.negated_risks
    assert any("negation conflict" in item for item in result.reason)


def test_none_of_conflict_blocks_severe_bleeding_protocol():
    engine = ProtocolEngine()
    canonical, intent = _intent_for("我流鼻血")
    bleeding_protocol = next(
        protocol
        for protocol in engine.protocols
        if protocol.get("protocol_id") == "prot_bleeding_control"
    )
    result = engine._score_protocol(
        bleeding_protocol,
        canonical,
        routed_tags=[],
        events=[],
        ctx=intent.to_dict(),
    )

    assert result.protocol_id == "prot_bleeding_control"
    assert result.matched is False
    assert result.negation_conflict is True
    assert result.protocol is None
    assert any("none_of" in item or "exclude" in item for item in result.reason)


def test_nosebleed_input_does_not_trigger_severe_bleeding_protocol():
    result = _match("我流鼻血")

    assert not (result.matched and result.protocol_id == "prot_bleeding_control")


def test_out_of_scope_input_has_low_protocol_confidence():
    result = _match("今天晚上吃什么")

    assert result.matched is False
    assert result.confidence < 0.2
    assert result.protocol is None


def test_collapse_aftershock_text_matches_protocol_with_explanation():
    result = _match("又在晃，墙在裂")

    assert result.matched is True
    assert result.protocol_id in {
        "prot_aftershock_immediate",
        "prot_secondary_collapse_risk",
    }
    assert result.confidence >= result.threshold
    assert any("keyword" in item or "scene" in item for item in result.reason)
    assert "collapse_aftershock" in result.protocol_risks


def test_event_trigger_can_match_aftershock_protocol_without_long_text():
    result = _match("晃", events=["imu_strong_shake"])

    assert result.matched is True
    assert result.protocol_id == "prot_aftershock_immediate"
    assert result.confidence >= result.threshold
    assert result.score_breakdown["event_hit"] == 1.0
    assert any("event trigger matched" in item for item in result.reason)


def test_protocol_confidence_uses_intent_context_signals():
    canonical, intent = _intent_for("地震后我被困住了，腿被压住，还流血")
    result = ProtocolEngine().match_with_score(
        canonical,
        routed_tags=["risk_bleeding", "body:腿", "scene:地震"],
        events=[],
        intent_context=intent,
    )

    assert result.matched is True
    assert result.protocol_id == "prot_bleeding_control"
    assert "severe_bleeding" in result.active_risks
    assert "trapped_or_crush" in result.active_risks
    assert "腿" in result.body_part_matches
    assert result.score_breakdown["risk_term_hit"] == 1.0
    assert result.score_breakdown["routed_tag_match"] == 1.0


def test_no_protocols_loaded_returns_clear_no_match(tmp_path: Path):
    empty = tmp_path / "protocols_empty.json"
    empty.write_text('{"protocols": []}', encoding="utf-8")

    result = ProtocolEngine(str(empty)).match_with_score("我的腿在流血")

    assert result.matched is False
    assert result.confidence == 0.0
    assert result.protocol is None
    assert result.reason == ["no protocols loaded"]
    assert result.threshold == ProtocolEngine.MATCH_THRESHOLD


def test_protocol_match_result_serializes_to_json():
    result = _match("我的腿在流血")
    payload = result.to_dict()

    json.dumps(payload, ensure_ascii=False)
    assert payload["confidence"] == result.confidence
    assert payload["reason"] == result.reason
    assert payload["protocol_id"] == "prot_bleeding_control"
    assert payload["matched_terms"] == result.matched_terms
    assert payload["negation_conflict"] is False
    assert "score_breakdown" in payload
    assert "threshold" in payload


def test_legacy_match_remains_compatible():
    protocol = ProtocolEngine().match("我的腿在流血", [], [])

    assert protocol is not None
    assert protocol["protocol_id"] == "prot_bleeding_control"


def test_legacy_match_does_not_fallback_on_negation_conflict():
    protocol = ProtocolEngine().match("腿疼但是没流血", [], [])

    assert protocol is None


def test_orchestrator_trace_contains_protocol_confidence():
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=_FakeRag(),
        protocol_engine=ProtocolEngine(),
        output_pipeline=_FakeOutput(),
        llm=_FakeLLM(),
    )

    session.handle("我的腿在流血")

    assert session.last_trace["protocol_id"] == "prot_bleeding_control"
    assert session.last_trace["protocol_confidence"] > 0.6
    assert "流血" in session.last_trace["matched_terms"]
    assert session.last_trace["reason"]
    assert session.last_trace["protocol_match"]["score_breakdown"]["keyword_hit"] == 1.0


def test_orchestrator_uses_match_with_score_not_legacy_match():
    protocol = _ProtocolSpy()
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=_FakeRag(),
        protocol_engine=protocol,
        output_pipeline=_FakeOutput(),
        llm=_FakeLLM(),
    )

    session.handle("退在留血")

    assert protocol.match_with_score_called is True
    assert protocol.match_called is False
    assert protocol.seen_text == "腿在流血"
    assert protocol.seen_intent_context.primary_intent == "severe_bleeding"
    assert session.last_trace["protocol_match"]["matched"] is False
