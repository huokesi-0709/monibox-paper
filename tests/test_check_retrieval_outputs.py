from __future__ import annotations

import json
from pathlib import Path

from benchmarks.rair_rag.downstream.check_retrieval_outputs import (
    check_retrieval_outputs,
)


def test_check_retrieval_outputs_reports_metrics_and_old_bert_warning(
    tmp_path: Path,
) -> None:
    retrieval_dir = tmp_path / "retrieval"
    report = tmp_path / "tables" / "retrieval_check_report.md"
    for system in ("vanilla-rag", "keyword-rag", "bert-rag", "rair-rag"):
        _write_summary(retrieval_dir / f"rair_test_{system}_summary.json", system)
    (retrieval_dir / "rair_test_bert-rag_predictions.jsonl").write_text(
        json.dumps(
            {
                "id": "x1",
                "trace": {
                    "risk_context": {
                        "trace": {
                            "baseline": "bert-multilabel local proxy without explicit negation"
                        }
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = check_retrieval_outputs(
        retrieval_dir=retrieval_dir,
        dataset="rair_test",
        out_path=report,
    )

    bert_row = next(row for row in result["rows"] if row["System"] == "bert-rag")
    assert bert_row["Status"] == "WARN"
    assert "must be rerun" in bert_row["Notes"]
    assert bert_row["NumCases"] == "2"
    assert bert_row["ProtocolAcc"] == "0.5000"
    assert report.exists()
    assert "BERT-RAG must be rerun" in report.read_text(encoding="utf-8")


def _write_summary(path: Path, system: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "system": system,
                "num_cases": 2,
                "metrics": {
                    "num_cases": 2,
                    "ProtocolAcc": 0.5,
                    "EvidenceHit@1": 0.25,
                    "EvidenceHit@3": 0.75,
                    "PFTR": 0.0,
                    "HRR": 1.0,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
