from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.baselines import get_method_config
from benchmarks.run_eval import _predict_with_session
from benchmarks.schema import BenchmarkCase
from runtime.guard import GuardResult
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.protocol_matcher import ProtocolMatchResult
from runtime.rag_engine import SearchResult
from runtime.trace import (
    InteractionTrace,
    TraceTopChunk,
    append_trace_jsonl,
    trace_to_dict,
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

    def __init__(self, results: list[SearchResult] | None = None):
        self.results = results if results is not None else [_result()]

    def is_vague_query(self, text: str) -> bool:
        del text
        return False

    def search(self, *args: Any, **kwargs: Any) -> list[SearchResult]:
        del args, kwargs
        return list(self.results)


class _NoMatchProtocol:
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


class _HitProtocol:
    def match_with_score(
        self,
        text: str,
        routed_tags: list[str],
        events: list[str],
        intent_context=None,
    ) -> ProtocolMatchResult:
        del text, routed_tags, events, intent_context
        protocol = {
            "protocol_id": "prot_bleeding_control",
            "name": "出血/流血-直接压迫止血",
            "priority": 95,
            "cooldown_sec": 0,
            "enable_qa": False,
            "actions": [
                {
                    "type": "tts",
                    "text": "直接按压伤口，减少活动。",
                }
            ],
        }
        return ProtocolMatchResult(
            matched=True,
            protocol_id="prot_bleeding_control",
            protocol_name="出血/流血-直接压迫止血",
            confidence=0.82,
            priority=95,
            matched_terms=["流血"],
            body_part_matches=["腿"],
            scene_matches=[],
            negation_conflict=False,
            reason=["keyword terms matched: ['流血']"],
            protocol=protocol,
            score_breakdown={"keyword_hit": 1.0},
            threshold=0.5,
            active_risks=["severe_bleeding"],
            negated_risks=[],
            protocol_risks=["severe_bleeding"],
        )


class _FakeOutput:
    def __init__(self) -> None:
        self.last_guard_result = None
        self.last_output_result = None

    def set_turn_context(self, context: dict) -> None:
        del context

    def emit(self, text: str, **kwargs: Any) -> str:
        del kwargs
        self.last_guard_result = GuardResult(level="allow", reasons=[], safe_text=text)
        self.last_output_result = {
            "raw_text": text,
            "final_text": text,
            "guard_level": "allow",
            "guard_reasons": [],
        }
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
    def generate(
        self, query: str, results: list[SearchResult], high_risk: bool, mem
    ) -> str:
        del results, high_risk, mem
        return f"rag reply for {query}"


def _result() -> SearchResult:
    return SearchResult(
        chunk_id="chunk_bleeding",
        display_id="D1",
        group_id="g1",
        text="腿部流血时先直接按压伤口，减少活动，等待救援。这是较长文本但 trace 只保留预览。",
        category="急救",
        sub_category="出血",
        dimension="safety",
        risk="severe_bleeding",
        scene="地震",
        source_id="src_test",
        status="启用",
        quality_score=5.0,
        priority=1,
        hardware_action_hint=None,
        distance=0.1,
        final_distance=0.1,
        tags_flat="|risk_bleeding|body:腿|",
        score_breakdown={
            "final_score": 0.9,
            "sim_vec": 0.9,
            "sim_sparse": 0.5,
            "quality": 1.0,
            "tag_match": 0.8,
            "risk_match": 1.0,
            "unsafe": 0.0,
            "redundancy": 0.0,
            "explanation": ["test breakdown"],
        },
    )


def _session(protocol=None, rag=None) -> MoniSession:
    session = MoniSession(
        "build/rag.db",
        SessionConfig(llm_path="", tts_enabled=False),
        rag=rag or _FakeRag(),
        protocol_engine=protocol or _NoMatchProtocol(),
        output_pipeline=_FakeOutput(),
        llm=_FakeLLM(),
        rag_generator=_FakeRagGenerator(),
    )
    session.rt.runtime_trace_enabled = False
    return session


def test_trace_to_dict_serializes_paper_trace() -> None:
    trace = InteractionTrace(
        case_id="case_1",
        suite="clean",
        method="hsc-rag-de",
        raw_text="我的腿在流血",
        canonical_text="我的腿在流血",
        input_normalization={"changed": False},
        intent_context={"primary_intent": "severe_bleeding"},
        protocol_match={"matched": True},
        top_chunks=[
            TraceTopChunk(
                rank=1,
                chunk_id="c1",
                source_id="src",
                text_preview="短证据",
                score_breakdown={"final_score": 0.8},
            )
        ],
        output_guard={"guard_level": "allow"},
        reply="先按压伤口。",
    )

    payload = trace_to_dict(trace)
    json.dumps(payload, ensure_ascii=False)
    assert payload["trace_version"] == "paper-trace-v1"
    assert payload["top_chunks"][0]["rank"] == 1


def test_append_trace_jsonl_writes_one_json_line(tmp_path: Path) -> None:
    out = tmp_path / "trace.jsonl"
    append_trace_jsonl(out, InteractionTrace(query_id="q1", reply="ok"))

    rows = out.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["query_id"] == "q1"


def test_protocol_path_trace_contains_input_intent_and_protocol_fields() -> None:
    session = _session(protocol=_HitProtocol(), rag=_FakeRag(results=[]))

    session.handle("退在留血")

    trace = session.last_trace
    assert trace["trace_version"] == "paper-trace-v1"
    assert trace["raw_text"] == "退在留血"
    assert trace["canonical_text"] == "腿在流血"
    assert trace["input_normalization"]["changed"] is True
    assert trace["corrections"]
    assert trace["intent_context"]["primary_intent"] == "severe_bleeding"
    assert "matched_terms" in trace["intent_context"]
    assert trace["protocol_match"]["matched"] is True
    assert trace["protocol_id"] == "prot_bleeding_control"
    assert trace["protocol_confidence"] == 0.82
    assert trace["protocol_match_reason"]


def test_rag_path_trace_contains_top_chunks_and_score_breakdown() -> None:
    session = _session(protocol=_NoMatchProtocol(), rag=_FakeRag(results=[_result()]))

    session.handle("我的腿在流血")

    trace = session.last_trace
    top = trace["top_chunks"][0]
    assert trace["decision"] == "rag_normal"
    assert top["rank"] == 1
    assert top["chunk_id"] == "chunk_bleeding"
    assert top["source_id"] == "src_test"
    assert top["category"] == "急救"
    assert top["sub_category"] == "出血"
    assert top["tags_flat"] == "|risk_bleeding|body:腿|"
    assert len(top["text_preview"]) <= 80
    assert top["score_breakdown"]["final_score"] == 0.9


def test_low_evidence_trace_contains_decision_and_bucket() -> None:
    session = _session(protocol=_NoMatchProtocol(), rag=_FakeRag(results=[]))

    session.handle("今天晚上吃什么")

    assert session.last_trace["decision"] == "low_evidence_rag_fallback"
    assert session.last_trace["low_evidence"] is True
    assert "bucket" in session.last_trace


def test_benchmark_prediction_trace_contains_metadata() -> None:
    session = _session(protocol=_NoMatchProtocol(), rag=_FakeRag(results=[_result()]))
    case = BenchmarkCase(id="case_trace", query="我的腿在流血")
    config = get_method_config("hsc-rag-de")

    prediction = _predict_with_session(
        case,
        session,
        config,
        profile="paper_eval",
        policy="scoring/policy_de.json",
        ablation=None,
        data="benchmarks/data/clean_dev.jsonl",
    )

    trace = prediction["trace"]
    assert trace["metadata"]["method"] == "hsc-rag-de"
    assert "disabled_modules" in trace["metadata"]
    assert trace["metadata"]["profile"] == "paper_eval"
    assert trace["metadata"]["policy"] == "scoring/policy_de.json"
    assert trace["metadata"]["suite"] == "clean"
    assert trace["case_id"] == "case_trace"
