from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from benchmarks.rair_rag.downstream.retrieval_eval import predict_case
from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence
from benchmarks.rair_rag.downstream.systems import DownstreamSystem


@dataclass
class _FakeSystem(DownstreamSystem):
    name: str = "rair-rag"
    last_trace: dict[str, Any] = field(default_factory=dict, init=False)

    def build_context(self, case: DownstreamCase) -> dict[str, Any]:
        return {}

    def build_retrieval_query(
        self, case: DownstreamCase, context: dict[str, Any]
    ) -> str:
        return case.raw_input

    def retrieve(
        self, case: DownstreamCase, rag_engine: object, topk: int = 5
    ) -> list[RetrievedEvidence]:
        self.last_trace = {
            "retrieval_query": case.raw_input,
            "risk_context": {
                "predicted_route": "route_respiratory_distress",
                "protocol_id": "prot_respiratory_distress",
            },
        }
        return [
            RetrievedEvidence(
                rank=1,
                chunk_id="wrong_top1",
                text="wrong",
                source_id="src_synth_deepseek_v1",
                protocol_id="prot_bleeding_control",
            ),
            RetrievedEvidence(
                rank=2,
                chunk_id="right_top2",
                text="right",
                source_id="WHO_BEC_2018",
                protocol_id="prot_respiratory_distress",
                matched_gold_protocol=True,
                matched_guideline_ref=True,
            ),
        ]


def test_protocol_acc_uses_retrieved_top1_not_routed_protocol() -> None:
    case = DownstreamCase(
        id="case_1",
        raw_input="need breathing help",
        canonical_input="need breathing help",
        expected_protocol_id="prot_respiratory_distress",
        guideline_refs=[{"source_id": "WHO_BEC_2018"}],
        risk_level="critical",
    )

    prediction = predict_case(
        case=case,
        system=_FakeSystem(),
        rag_engine=object(),
        topk=2,
    )

    assert prediction["routed_protocol_id"] == "prot_respiratory_distress"
    assert prediction["predicted_protocol_id"] == "prot_bleeding_control"
    assert prediction["metrics"]["ProtocolAcc"] == 0.0
    assert prediction["metrics"]["ProtocolEvidenceHit@3"] == 1.0
    assert prediction["trace"]["protocol_prediction_source"] == "retrieval_top1"
    assert prediction["trace"]["source_id_diagnostics"]["matched_source_ids"] == [
        "WHO_BEC_2018"
    ]
