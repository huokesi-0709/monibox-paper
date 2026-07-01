from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from app.config import settings
from benchmarks.rair_rag.downstream.metrics import (
    compute_case_metrics,
    compute_retrieval_metrics,
)
from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence
from benchmarks.rair_rag.downstream.systems import (
    BertRagSystem,
    DownstreamSystem,
    KeywordRagSystem,
    RairRagSystem,
    VanillaRagSystem,
)
from runtime.rag_engine import RagEngine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "retrieval"
DEFAULT_TABLES_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "tables"
DEFAULT_DATA = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
)
SUPPORTED_SYSTEMS = {
    "vanilla-rag": VanillaRagSystem,
    "keyword-rag": KeywordRagSystem,
    "bert-rag": BertRagSystem,
    "rair-rag": RairRagSystem,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAIR-RAG downstream retrieval evaluation without LLMs."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--system", choices=sorted(SUPPORTED_SYSTEMS), required=True)
    parser.add_argument("--rag-db", type=Path, default=_default_rag_db_path())
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    out_path = args.out or _default_out_path(args.data, args.system)
    summary_path = args.summary or _default_summary_path(args.data, args.system)
    try:
        summary = run_retrieval_eval(
            data_path=args.data,
            system_name=args.system,
            rag_db_path=args.rag_db,
            topk=args.topk,
            out_path=out_path,
            summary_path=summary_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_retrieval_eval(
    *,
    data_path: Path,
    system_name: str,
    rag_db_path: Path,
    topk: int,
    out_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    if topk <= 0:
        msg = "--topk must be a positive integer"
        raise ValueError(msg)
    if system_name not in SUPPORTED_SYSTEMS:
        allowed = ", ".join(sorted(SUPPORTED_SYSTEMS))
        msg = f"unsupported system {system_name}; choose one of {allowed}"
        raise ValueError(msg)
    if not rag_db_path.exists():
        msg = (
            f"RAG database not found: {rag_db_path}. "
            "Please run `uv run monibox-build-rag` first, or pass --rag-db / set "
            "RAG_DB_PATH to an existing rag.db file."
        )
        raise FileNotFoundError(msg)

    cases = load_downstream_cases(data_path)
    system = SUPPORTED_SYSTEMS[system_name]()
    rag_engine = RagEngine(str(rag_db_path))
    predictions = [
        predict_case(case=case, system=system, rag_engine=rag_engine, topk=topk)
        for case in cases
    ]
    metrics = compute_retrieval_metrics(cases, predictions)
    summary = {
        "data": str(data_path),
        "system": system_name,
        "rag_db": str(rag_db_path),
        "topk": topk,
        "num_cases": len(cases),
        "metrics": metrics,
    }
    write_jsonl(out_path, predictions)
    write_json(summary_path, summary)
    write_retrieval_results_table(summary_path.parent, DEFAULT_TABLES_DIR)
    return summary


def predict_case(
    *, case: DownstreamCase, system: DownstreamSystem, rag_engine: RagEngine, topk: int
) -> dict[str, Any]:
    evidence = system.retrieve(case=case, rag_engine=rag_engine, topk=topk)
    trace = dict(system.last_trace)
    risk_context = _dict_value(trace.get("risk_context"))
    retrieval_query = str(trace.get("retrieval_query") or case.raw_input)
    predicted_protocol_id = _predicted_protocol_id(
        system=system, risk_context=risk_context, evidence=evidence
    )
    prediction = {
        "id": case.id,
        "system": system.name,
        "raw_input": case.raw_input,
        "retrieval_query": retrieval_query,
        "risk_context": risk_context,
        "retrieved_evidence": [item.to_dict() for item in evidence],
        "predicted_protocol_id": predicted_protocol_id,
        "trace": {
            **trace,
            "matching_mode": _matching_mode(evidence, case),
            "gold": {
                "expected_protocol_id": case.expected_protocol_id,
                "guideline_refs": case.guideline_refs,
                "should_not_trigger": case.should_not_trigger,
                "risk_level": case.risk_level,
            },
        },
    }
    prediction["metrics"] = compute_case_metrics(case, prediction)
    return prediction


def load_downstream_cases(path: Path) -> list[DownstreamCase]:
    cases: list[DownstreamCase] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            cases.append(DownstreamCase.from_json_line(line))
        except ValueError as exc:
            msg = f"{path}:line {lineno}: {exc}"
            raise ValueError(msg) from exc
    return cases


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_retrieval_results_table(summary_dir: Path, tables_dir: Path) -> None:
    rows = []
    for path in sorted(summary_dir.glob("*_summary.json")):
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        metrics = summary.get("metrics")
        if not isinstance(metrics, dict):
            continue
        rows.append(
            {
                "dataset": Path(str(summary.get("data") or "")).stem,
                "system": str(summary.get("system") or ""),
                "ProtocolAcc": float(metrics.get("ProtocolAcc") or 0.0),
                "EvidenceHit@1": float(metrics.get("EvidenceHit@1") or 0.0),
                "EvidenceHit@3": float(metrics.get("EvidenceHit@3") or 0.0),
                "PFTR": float(metrics.get("PFTR") or 0.0),
                "HRR": float(metrics.get("HRR") or 0.0),
                "AvgRetrieved": float(metrics.get("AvgRetrieved") or 0.0),
            }
        )

    tables_dir.mkdir(parents=True, exist_ok=True)
    table_path = tables_dir / "retrieval_results.md"
    header = (
        "| Dataset | System | ProtocolAcc | EvidenceHit@1 | EvidenceHit@3 | "
        "PFTR | HRR | AvgRetrieved |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    lines.extend(
        (
            "| {dataset} | {system} | {ProtocolAcc:.4f} | {EvidenceHit@1:.4f} | "
            "{EvidenceHit@3:.4f} | {PFTR:.4f} | {HRR:.4f} | {AvgRetrieved:.2f} |".format(
                **row
            )
        )
        for row in rows
    )
    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _predicted_protocol_id(
    *,
    system: DownstreamSystem,
    risk_context: dict[str, Any],
    evidence: list[RetrievedEvidence],
) -> str | None:
    context_protocol = risk_context.get("protocol_id")
    if system.name != "vanilla-rag" and context_protocol:
        return str(context_protocol)
    if evidence and evidence[0].protocol_id:
        return evidence[0].protocol_id
    return str(context_protocol) if context_protocol else None


def _matching_mode(evidence: list[RetrievedEvidence], case: DownstreamCase) -> str:
    if not evidence:
        return "no_evidence"
    if any(item.protocol_id == case.expected_protocol_id for item in evidence):
        return "protocol_id_or_risk_weak_match"
    if any(item.matched_guideline_ref for item in evidence):
        return "guideline_source_id_match"
    return "no_gold_match"


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _default_rag_db_path() -> Path:
    return Path(os.getenv("RAG_DB_PATH") or settings.rag_db_path)


def _default_out_path(data_path: Path, system_name: str) -> Path:
    return DEFAULT_OUT_DIR / f"{data_path.stem}_{system_name}_predictions.jsonl"


def _default_summary_path(data_path: Path, system_name: str) -> Path:
    return DEFAULT_OUT_DIR / f"{data_path.stem}_{system_name}_summary.json"


if __name__ == "__main__":
    main()
