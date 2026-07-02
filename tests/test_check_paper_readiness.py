from __future__ import annotations

import json
from pathlib import Path

from benchmarks.rair_rag.downstream.check_paper_readiness import check_paper_readiness


def test_check_paper_readiness_reports_missing_real_bert(tmp_path: Path) -> None:
    root = tmp_path
    _write_json(
        root / "build/downstream_eval/generation/reference/reference_generation_manifest.json",
        {"model": "qwen-plus", "outputs": ["a.jsonl"]},
    )
    for path in (
        root / "build/downstream_eval/generation/reference/rair_test_vanilla-rag_reference-llm_outputs.jsonl",
        root / "build/downstream_eval/generation/reference/rair_test_rair-rag_reference-llm_outputs.jsonl",
        root / "build/downstream_eval/generation/local/rair_test_vanilla-rag_local-llm_outputs.jsonl",
        root / "build/downstream_eval/generation/local/rair_test_rair-rag_local-llm_outputs.jsonl",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"id":"x"}\n', encoding="utf-8")
    for path in (
        root / "build/downstream_eval/tables/generation_safety_results.md",
        root / "build/downstream_eval/tables/generation_latency_results.md",
        root / "build/downstream_eval/tables/retrieval_main_results.md",
        root / "build/rair_eval/tables/policy_parameters.md",
        root / "build/rair_eval/error_analysis/negation_failures.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")

    result = check_paper_readiness(
        root=root,
        out_path=root / "build/paper_readiness_report.md",
    )

    assert result["overall"] == "FAIL"
    assert result["status_counts"]["FAIL"] == 1
    bert = next(item for item in result["results"] if item["item"] == "Real BERT test summary")
    assert bert["status"] == "FAIL"
    assert "Missing" in bert["detail"]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
