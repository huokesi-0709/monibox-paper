from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.rair_rag.downstream.generation_eval import run_generation_eval
from benchmarks.rair_rag.downstream.llm_clients import BaseGenerator


class StubGenerator(BaseGenerator):
    model_path = "models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf"

    def generate(self, prompt: str) -> str:
        return json.dumps(
            {
                "protocol_id": "prot_respiratory_distress",
                "reply": "ok",
                "safety_notes": [],
                "used_evidence": [],
            },
            ensure_ascii=False,
        )


def test_generation_eval_local_metadata_resume_and_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "cases.jsonl"
    rag_db = tmp_path / "rag.db"
    out = tmp_path / "outputs.jsonl"
    summary = tmp_path / "summary.json"
    data.write_text(json.dumps(_case(), ensure_ascii=False) + "\n", encoding="utf-8")
    rag_db.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "benchmarks.rair_rag.downstream.generation_eval.RagEngine",
        lambda _path: object(),
    )
    monkeypatch.setattr(
        "benchmarks.rair_rag.downstream.systems.DownstreamSystem.retrieve",
        lambda self, case, rag_engine, topk=5: [],
    )

    first = run_generation_eval(
        data_path=data,
        system_name="vanilla-rag",
        generator_name="local-llm",
        rag_db_path=rag_db,
        topk=1,
        out_path=out,
        summary_path=summary,
        generator=StubGenerator(),
    )

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert first["completed_cases"] == 1
    assert rows[0]["model"] == "Qwen1.5-0.5B-Chat-Q4_K_M"
    assert rows[0]["setting"] == "edge_local"
    assert rows[0]["status"] == "ok"
    assert rows[0]["error"] is None
    assert isinstance(rows[0]["latency_ms"], float)

    with pytest.raises(FileExistsError, match="Output already exists"):
        run_generation_eval(
            data_path=data,
            system_name="vanilla-rag",
            generator_name="local-llm",
            rag_db_path=rag_db,
            topk=1,
            out_path=out,
            summary_path=summary,
            generator=StubGenerator(),
        )

    resumed = run_generation_eval(
        data_path=data,
        system_name="vanilla-rag",
        generator_name="local-llm",
        rag_db_path=rag_db,
        topk=1,
        out_path=out,
        summary_path=summary,
        generator=StubGenerator(),
        resume=True,
    )
    assert resumed["skipped_cases"] == 1
    assert len(out.read_text(encoding="utf-8").splitlines()) == 1

    overwritten = run_generation_eval(
        data_path=data,
        system_name="vanilla-rag",
        generator_name="local-llm",
        rag_db_path=rag_db,
        topk=1,
        out_path=out,
        summary_path=summary,
        generator=StubGenerator(),
        overwrite=True,
    )
    assert overwritten["completed_cases"] == 1
    assert len(out.read_text(encoding="utf-8").splitlines()) == 1


def _case() -> dict[str, object]:
    return {
        "id": "case_1",
        "raw_input": "我喘不上气",
        "canonical_input": "我喘不上气",
        "expected_protocol_id": "prot_respiratory_distress",
        "expected_route": "route_respiratory_distress",
        "positive_risks": ["respiratory_distress"],
        "negated_risks": [],
        "primary_intent": "respiratory_distress",
        "secondary_intents": [],
        "operational_constraints": [],
        "should_not_trigger": [],
        "suppressed_protocols": [],
        "guideline_refs": [],
        "risk_level": "critical",
        "perturbation_types": ["clean_control"],
    }
