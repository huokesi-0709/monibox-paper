from __future__ import annotations

import json
from typing import ClassVar

from runtime.guard import GuardResult
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.trace import (
    InteractionTrace,
    TraceTopChunk,
    append_trace_jsonl,
    trace_to_dict,
)


class _Route:
    tags: ClassVar[list[str]] = ["出血"]
    cross_dimension = False
    dimension = "medical"


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


class _FakeOutput:
    def __init__(self, guard_result: GuardResult | None = None):
        self.last_guard_result = None
        self.last_output_result = None
        self.guard_result = guard_result or GuardResult(
            level="allow", reasons=[], safe_text=""
        )

    def set_turn_context(self, context: dict) -> None:
        del context

    def emit(self, text: str, **kwargs) -> str:
        del kwargs
        self.last_guard_result = self.guard_result
        self.last_output_result = {
            "raw_text": text,
            "final_text": self.guard_result.safe_text or text,
            "guard_level": self.guard_result.level,
            "guard_reasons": list(self.guard_result.reasons),
        }
        return self.guard_result.safe_text or text


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


def _session(output: _FakeOutput | None = None) -> MoniSession:
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=_FakeRag(),
        protocol_engine=_FakeProtocol(),
        output_pipeline=output or _FakeOutput(),
        llm=_FakeLLM(),
    )
    session.rt.runtime_trace_enabled = False
    return session


def test_interaction_trace_can_convert_to_json_dict(tmp_path):
    trace = InteractionTrace(
        query_id="q1",
        raw_text="我的腿在流血",
        canonical_text="我的腿在流血",
        route={"tags": ["出血"]},
        primary_intent="severe_bleeding",
        risk_score=0.9,
        protocol_id="prot_bleeding_control",
        protocol_confidence=0.72,
        evidence_score=0.81,
        top_chunks=[
            TraceTopChunk(
                chunk_id="c1",
                final_distance=0.19,
                score_breakdown={"final_score": 0.81},
            )
        ],
        guard_level="allow",
        latency_ms=12.5,
        reply="先压住伤口。",
    )

    payload = trace_to_dict(trace)
    json.dumps(payload, ensure_ascii=False)

    out = tmp_path / "trace.jsonl"
    append_trace_jsonl(out, trace)
    assert out.read_text(encoding="utf-8").strip()


def test_orchestrator_last_trace_contains_paper_schema_for_normal_input():
    session = _session()

    reply = session.handle("今天晚上吃什么")

    assert session.last_trace["raw_text"] == "今天晚上吃什么"
    assert session.last_trace["canonical_text"] == "今天晚上吃什么"
    assert session.last_trace["route"]["tags"] == ["出血"]
    assert session.last_trace["latency_ms"] >= 0
    assert session.last_trace["reply"] == reply


def test_guard_reasons_are_captured_in_trace():
    output = _FakeOutput(
        GuardResult(
            level="block",
            reasons=["tourniquet_instruction"],
            safe_text="这类高风险处置先不要做。",
        )
    )
    session = _session(output)

    session.handle("今天晚上吃什么")

    assert session.last_trace["guard_level"] == "block"
    assert session.last_trace["guard_reasons"] == ["tourniquet_instruction"]
