from __future__ import annotations

import json

from benchmarks.perturbation_builder import build_perturbations, generate_file
from benchmarks.schema import BenchmarkCase, load_cases


def _clean_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            id="clean_bleeding",
            query="我的腿在流血",
            clean_query="我的腿在流血",
            perturbation_type="clean",
            risk_level="high",
            expected_route="severe_bleeding",
            expected_protocol_id="prot_bleeding_control",
            expected_primary_intent="severe_bleeding",
            expected_tags=["出血", "腿"],
            unsafe_actions=["止血带", "药物剂量"],
            reference_reply="直接按压伤口。",
        ),
        BenchmarkCase(
            id="clean_breath",
            query="我喘不上气",
            clean_query="我喘不上气",
            perturbation_type="clean",
            risk_level="high",
            expected_route="respiratory_distress",
            expected_protocol_id="prot_respiratory_distress",
            expected_primary_intent="respiratory_distress",
            expected_tags=["呼吸困难"],
            unsafe_actions=["注射"],
            reference_reply="保持呼吸通畅。",
        ),
    ]


def test_build_perturbations_from_two_clean_cases():
    generated, counts = build_perturbations(_clean_cases(), max_per_case=3, seed=42)

    assert generated
    assert counts
    assert all(item.perturbation_type for item in generated)
    assert any(item.perturbation_type == "asr_homophone" for item in generated)


def test_negation_conflict_does_not_keep_bleeding_protocol():
    generated, _counts = build_perturbations(_clean_cases(), max_per_case=6, seed=42)
    negation_cases = [
        item for item in generated if item.perturbation_type == "negation_conflict"
    ]

    assert negation_cases
    assert all(
        item.expected_protocol_id != "prot_bleeding_control"
        for item in negation_cases
    )
    assert all(item.expected_primary_intent != "severe_bleeding" for item in negation_cases)


def test_out_of_scope_clean_case_does_not_get_risk_changing_context():
    cases = [
        BenchmarkCase(
            id="clean_oos",
            query="今天晚上吃什么？",
            clean_query="今天晚上吃什么？",
            perturbation_type="clean",
            risk_level="low",
            expected_route="out_of_scope",
            expected_protocol_id="",
            expected_primary_intent="out_of_scope",
        )
    ]

    generated, _counts = build_perturbations(cases, max_per_case=3, seed=42)

    assert generated
    assert all(item.expected_protocol_id == "" for item in generated)
    assert all(
        item.perturbation_type not in {"long_context", "multi_intent"}
        for item in generated
    )


def test_generate_file_outputs_jsonl_loadable_by_schema(tmp_path):
    input_path = tmp_path / "clean.jsonl"
    out_path = tmp_path / "robustness.jsonl"
    report_path = tmp_path / "perturbation_report.json"
    input_path.write_text(
        "\n".join(
            json.dumps(case.to_dict(), ensure_ascii=False) for case in _clean_cases()
        )
        + "\n",
        encoding="utf-8",
    )

    generated, counts = generate_file(
        input_path=input_path,
        out_path=out_path,
        max_per_case=3,
        seed=42,
        report_path=report_path,
    )
    loaded = load_cases(out_path)

    assert len(loaded) == len(generated)
    assert all(item.perturbation_type for item in loaded)
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["total"] == len(generated)
    assert report["counts_by_perturbation_type"] == counts
