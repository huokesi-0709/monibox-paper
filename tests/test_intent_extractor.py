from __future__ import annotations

from runtime.intent_extractor import IntentExtractor
from runtime.input_normalizer import InputNormalizer
from runtime.orchestrator import MoniSession, SessionConfig


class _Route:
    tags: list[str] = []
    cross_dimension = False
    dimension = None


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
        return None


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


def test_out_of_scope_input_has_low_risk():
    ctx = IntentExtractor().extract("今天晚上吃什么")

    assert ctx.primary_intent == "out_of_scope"
    assert ctx.risk_score <= 0.1
    assert ctx.secondary_intents == []


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


def test_normalized_text_can_feed_intent_extractor():
    normalized = InputNormalizer().normalize("穿不上气")
    ctx = IntentExtractor().extract(normalized.canonical_text)

    assert normalized.canonical_text == "喘不上气"
    assert ctx.primary_intent == "respiratory_distress"
