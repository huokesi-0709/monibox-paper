from __future__ import annotations

from runtime.intent_extractor import IntentExtractor
from runtime.input_normalizer import InputNormalizer
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.protocol_matcher import ProtocolEngine


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


def _match(text: str):
    canonical = InputNormalizer().normalize(text).canonical_text
    intent = IntentExtractor().extract(canonical)
    return ProtocolEngine().match_with_score(
        canonical,
        routed_tags=[],
        events=[],
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


def test_negated_bleeding_is_not_high_confidence():
    result = _match("腿疼但是没流血")

    assert not (
        result.protocol_id == "prot_bleeding_control" and result.confidence > 0.6
    )
    assert result.confidence < 0.6
    assert result.negation_conflict is True


def test_out_of_scope_input_has_low_protocol_confidence():
    result = _match("今天晚上吃什么")

    assert result.matched is False
    assert result.confidence < 0.2


def test_legacy_match_remains_compatible():
    protocol = ProtocolEngine().match("我的腿在流血", [], [])

    assert protocol is not None
    assert protocol["protocol_id"] == "prot_bleeding_control"


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
