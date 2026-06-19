from __future__ import annotations

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
    seen_text = ""

    def match(self, text: str, routed_tags: list[str], events: list[str]):
        del routed_tags, events
        self.seen_text = text
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


def test_asr_leg_bleeding_misrecognition_is_corrected():
    normalized = InputNormalizer().normalize("退在留血")

    assert normalized.canonical_text == "腿在流血"
    assert any(
        item.source == "退在留血" and item.target == "腿在流血"
        for item in normalized.corrections
    )


def test_breathing_misrecognition_is_corrected():
    normalized = InputNormalizer().normalize("穿不上气")

    assert normalized.canonical_text == "喘不上气"
    assert any(
        item.source == "穿不上气" and item.target == "喘不上气"
        for item in normalized.corrections
    )


def test_repeated_rescue_term_is_collapsed_after_correction():
    normalized = InputNormalizer().normalize("救命救命救命我喘不上气")

    assert normalized.canonical_text == "救命我喘不上气"
    assert "救命" in normalized.repeated_terms_collapsed


def test_empty_input_stays_empty():
    normalized = InputNormalizer().normalize(" 　\t ")

    assert normalized.raw_text == " 　\t "
    assert normalized.canonical_text == ""
    assert normalized.corrections == []
    assert normalized.noise_removed == []
    assert normalized.repeated_terms_collapsed == []


def test_clean_input_is_not_damaged():
    normalized = InputNormalizer().normalize("我腿疼但是没有流血")

    assert normalized.canonical_text == "我腿疼但是没有流血"
    assert normalized.corrections == []
    assert normalized.noise_removed == []
    assert normalized.repeated_terms_collapsed == []


def test_required_builtin_corrections_are_covered():
    cases = {
        "留血": "流血",
        "穿不过气": "喘不过气",
        "旧我": "救我",
        "地真": "地震",
    }

    normalizer = InputNormalizer()
    for raw, canonical in cases.items():
        assert normalizer.normalize(raw).canonical_text == canonical


def test_orchestrator_uses_canonical_text_and_keeps_trace():
    protocol = _FakeProtocol()
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
    assert session.last_trace["raw_text"] == "退在留血"
    assert session.last_trace["canonical_text"] == "腿在流血"
    assert session.last_trace["corrections"][0]["source"] == "退在留血"
