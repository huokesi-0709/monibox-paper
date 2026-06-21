from __future__ import annotations

from typing import Any

from runtime.input_normalizer import InputNormalizer
from runtime.intent_extractor import IntentExtractor
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.protocol_matcher import ProtocolMatchResult


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


class _FakeProtocol:
    def match(self, text: str, routed_tags: list[str], events: list[str]):
        del text, routed_tags, events
        return


class _FakeProtocolWithScore:
    seen_text = ""
    seen_intent_context: Any = None

    def match_with_score(
        self,
        text: str,
        routed_tags: list[str],
        events: list[str],
        intent_context=None,
    ) -> ProtocolMatchResult:
        del routed_tags, events
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
            reason=["test fake protocol"],
            protocol=None,
        )


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


def test_long_multi_intent_selects_severe_bleeding_as_primary():
    ctx = IntentExtractor().extract(
        "我刚才地震被困在废墟里，手机快没电了，腿被压住了，好像还流血，我也很害怕。"
    )

    assert ctx.primary_intent == "severe_bleeding"
    assert "trapped_or_crush" in ctx.secondary_intents
    assert "low_battery" in ctx.secondary_intents
    assert "panic" in ctx.secondary_intents
    assert "腿" in ctx.body_parts
    assert "地震" in ctx.scene_terms
    assert ctx.risk_score > 0.8
    assert any(item["term"] == "流血" for item in ctx.matched_terms)


def test_respiratory_distress_wins_over_cold_and_thirst():
    ctx = IntentExtractor().extract("我好冷，又很渴，还喘不上气")

    assert ctx.primary_intent == "respiratory_distress"
    assert "hypothermia" in ctx.secondary_intents
    assert "dehydration" in ctx.secondary_intents
    assert ctx.primary_risk_score == 1.0


def test_negated_bleeding_does_not_become_primary():
    ctx = IntentExtractor().extract("腿疼但是没流血")

    assert ctx.primary_intent != "severe_bleeding"
    assert ctx.primary_intent == "pain_or_injury"
    assert "severe_bleeding" in ctx.negated_risks
    assert any(
        item["intent"] == "severe_bleeding" and item["negated"]
        for item in ctx.matched_terms
    )


def test_multiple_negated_high_risks_do_not_become_primary():
    ctx = IntentExtractor().extract("没流血，也没有喘不上气，但腿疼")

    assert ctx.primary_intent == "pain_or_injury"
    assert ctx.primary_intent not in {"severe_bleeding", "respiratory_distress"}
    assert "severe_bleeding" in ctx.negated_risks
    assert "respiratory_distress" in ctx.negated_risks


def test_negated_respiratory_distress_is_not_active():
    ctx = IntentExtractor().extract("我没有喘不上气")

    assert ctx.primary_intent == "out_of_scope"
    assert "respiratory_distress" in ctx.negated_risks
    assert all(
        item["intent"] != "respiratory_distress" or item["negated"]
        for item in ctx.matched_terms
    )


def test_negated_trapped_phrase_allows_low_battery_primary():
    ctx = IntentExtractor().extract("我不是被困，就是手机快没电了")

    assert ctx.primary_intent == "low_battery"
    assert "trapped_or_crush" in ctx.negated_risks
    assert "trapped_or_crush" not in ctx.secondary_intents


def test_out_of_scope_input_has_low_risk():
    ctx = IntentExtractor().extract("今天晚上吃什么")

    assert ctx.primary_intent == "out_of_scope"
    assert ctx.risk_score <= 0.1
    assert ctx.secondary_intents == []
    assert "out_of_scope" in ctx.tags
    assert "medical_high_risk" not in ctx.tags


def test_safe_common_text_does_not_trigger_high_risk():
    ctx = IntentExtractor().extract("我没事，今天晚上吃什么")

    assert ctx.primary_intent == "out_of_scope"
    assert ctx.risk_score <= 0.1
    assert ctx.to_dict()["has_high_risk_intent"] is False


def test_multi_intent_respiratory_distress_wins_over_cold_and_thirst():
    ctx = IntentExtractor().extract("我喘不上气，还很冷，也很渴")

    assert ctx.primary_intent == "respiratory_distress"
    assert "hypothermia" in ctx.secondary_intents
    assert "dehydration" in ctx.secondary_intents


def test_trapped_bleeding_multi_intent_uses_priority_order():
    ctx = IntentExtractor().extract("地震后我被困住了，腿被压住，还流血")

    assert ctx.primary_intent == "severe_bleeding"
    assert "trapped_or_crush" in ctx.secondary_intents
    assert "risk_bleeding" in ctx.tags
    assert "body:腿" in ctx.tags
    assert "scene:地震" in ctx.tags


def test_trapped_intent_wins_over_low_battery():
    ctx = IntentExtractor().extract("手机快没电了，我还被困着")

    assert ctx.primary_intent == "trapped_or_crush"
    assert "low_battery" in ctx.secondary_intents


def test_head_or_consciousness_intent():
    ctx = IntentExtractor().extract("我头很晕，眼前发黑")

    assert ctx.primary_intent == "head_or_consciousness"
    assert "头" in ctx.body_parts


def test_collapse_aftershock_intent():
    ctx = IntentExtractor().extract("又在晃，墙在裂")

    assert ctx.primary_intent == "collapse_aftershock"


def test_hypothermia_wins_over_panic():
    ctx = IntentExtractor().extract("我好冷，一直发抖，还很害怕")

    assert ctx.primary_intent == "hypothermia"
    assert "panic" in ctx.secondary_intents


def test_body_parts_scene_terms_and_tags_are_explainable():
    ctx = IntentExtractor().extract("地震后废墟里，我腿和手都疼，头也疼，胸口闷")

    for part in ["腿", "手", "头", "胸口"]:
        assert part in ctx.body_parts
        assert f"body:{part}" in ctx.tags
    for scene in ["地震", "废墟"]:
        assert scene in ctx.scene_terms
        assert f"scene:{scene}" in ctx.tags


def test_matched_terms_include_positions_and_trace_stats():
    text = "我喘不上气，还很冷"
    ctx = IntentExtractor().extract(text)
    term = next(item for item in ctx.matched_terms if item["term"] == "喘不上气")

    assert term["start"] == text.index("喘不上气")
    assert term["end"] == term["start"] + len("喘不上气")
    payload = ctx.to_dict()
    assert payload["num_active_intents"] == 2
    assert payload["num_secondary_intents"] == 1
    assert payload["num_negated_risks"] == 0
    assert payload["has_high_risk_intent"] is True


def test_orchestrator_trace_contains_intent_context():
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=_FakeRag(),
        protocol_engine=_FakeProtocol(),
        output_pipeline=_FakeOutput(),
        llm=_FakeLLM(),
    )

    session.handle("退在留血")

    assert session.last_trace["canonical_text"] == "腿在流血"
    assert session.last_trace["primary_intent"] == "severe_bleeding"
    assert session.last_trace["intent_context"]["primary_intent"] == "severe_bleeding"
    assert session.last_trace["intent_context"]["has_high_risk_intent"] is True


def test_orchestrator_passes_canonical_text_and_intent_context_to_protocol():
    protocol = _FakeProtocolWithScore()
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=_FakeRag(),
        protocol_engine=protocol,
        output_pipeline=_FakeOutput(),
        llm=_FakeLLM(),
    )

    session.handle("退在留血")

    assert protocol.seen_text == "腿在流血"
    assert protocol.seen_intent_context.primary_intent == "severe_bleeding"
    assert session.last_trace["primary_intent"] == "severe_bleeding"
    assert session.last_trace["intent_risk_score"] > 0


def test_normalized_text_can_feed_intent_extractor():
    normalized = InputNormalizer().normalize("穿不上气")
    ctx = IntentExtractor().extract(normalized.canonical_text)

    assert normalized.canonical_text == "喘不上气"
    assert ctx.primary_intent == "respiratory_distress"
