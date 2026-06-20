from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from benchmarks.baselines import baseline_reply
from benchmarks.metrics import compute_all_metrics
from benchmarks.schema import BenchmarkCase, load_cases
from runtime.input_normalizer import InputNormalizer
from runtime.intent_extractor import IntentExtractor
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.primitives import WorkingMemory
from runtime.protocol_matcher import ProtocolEngine
from runtime.runtime_config import load_runtime_config
from runtime.scoring import load_policy


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _profile_name(profile: str | None, profile_file: str | None) -> str:
    if profile:
        return profile
    if profile_file:
        return Path(profile_file).stem
    return "paper_eval"


def _default_data_for_suite(suite: str) -> str:
    if suite == "robust":
        return "benchmarks/data/robustness_dev.jsonl"
    return "benchmarks/data/clean_dev.jsonl"


def _default_out(output_dir: str, suite: str, method: str) -> Path:
    return _resolve(output_dir) / f"{suite}_{method}_predictions.jsonl"


def _default_summary(output_dir: str, suite: str, method: str) -> Path:
    return _resolve(output_dir) / f"{suite}_{method}_summary.csv"


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            f.write("\n")


def _write_summary(path: str | Path, summary: dict[str, Any]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    json_path = out.with_suffix(".json")
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _create_session(profile: str, policy_path: str | None) -> MoniSession:
    os.environ["RUNTIME_PROFILE"] = profile
    cfg = load_runtime_config(profile)
    session = MoniSession(
        str(PROJECT_ROOT / cfg.__dict__.get("rag_db_path", "build/rag.db")),
        SessionConfig(llm_path="", tts_enabled=bool(cfg.tts_backend)),
    )
    if policy_path and hasattr(session.rag, "hsc_policy"):
        session.rag.hsc_policy = load_policy(policy_path)
    return session


def _reset_session_for_case(session: MoniSession) -> None:
    session.pending_bucket = None
    session.pending_until = 0.0
    session.current_interaction_id = None
    session.last_trace = {}
    session._input_trace = {}

    if hasattr(session.proto_handler, "clear_state"):
        session.proto_handler.clear_state()
    if hasattr(session.proto_handler, "_prot_state"):
        session.proto_handler._prot_state.clear()

    session.mem = WorkingMemory()
    if hasattr(session.output, "mem"):
        session.output.mem = session.mem
    if hasattr(session.output, "last_guard_result"):
        session.output.last_guard_result = None
    if hasattr(session.output, "last_output_result"):
        session.output.last_output_result = None
    if hasattr(session.output, "vb") and hasattr(session.output.vb, "rr_index"):
        session.output.vb.rr_index.clear()


def _predict_with_baseline(case: BenchmarkCase) -> dict[str, Any]:
    normalizer = InputNormalizer()
    intent_extractor = IntentExtractor()
    protocol_engine = ProtocolEngine()

    normalized = normalizer.normalize(case.query)
    intent = intent_extractor.extract(normalized.canonical_text)
    protocol = protocol_engine.match_with_score(
        normalized.canonical_text,
        routed_tags=intent.tags,
        events=[],
        intent_context=intent,
    )
    reply = baseline_reply(case)
    trace = {
        "query_id": case.id,
        "raw_text": normalized.raw_text,
        "canonical_text": normalized.canonical_text,
        "corrections": [item.to_dict() for item in normalized.corrections],
        "route": {"tags": intent.tags},
        "primary_intent": intent.primary_intent,
        "secondary_intents": intent.secondary_intents,
        "risk_score": intent.risk_score,
        "protocol_id": protocol.protocol_id,
        "protocol_confidence": protocol.confidence,
        "evidence_score": None,
        "top_chunks": [],
        "guard_level": None,
        "guard_reasons": [],
        "latency_ms": 0.0,
        "reply": reply,
        "metadata": {"method": "baseline"},
    }
    return {
        "case": case.to_dict(),
        "case_id": case.id,
        "query": case.query,
        "method": "baseline",
        "reply": reply,
        "trace": trace,
        "predicted_route": intent.primary_intent,
        "primary_intent": intent.primary_intent,
        "protocol_id": protocol.protocol_id,
        "latency_ms": 0.0,
    }


def _predict_with_session(
    case: BenchmarkCase, session: MoniSession, method: str
) -> dict[str, Any]:
    _reset_session_for_case(session)
    reply = session.handle(case.query)
    trace = dict(session.last_trace)
    return {
        "case": case.to_dict(),
        "case_id": case.id,
        "query": case.query,
        "method": method,
        "reply": reply,
        "trace": trace,
        "predicted_route": trace.get("primary_intent"),
        "primary_intent": trace.get("primary_intent"),
        "protocol_id": trace.get("protocol_id"),
        "latency_ms": trace.get("latency_ms"),
    }


def run_eval(
    data: str | Path,
    method: str = "hsc-rag-de",
    policy: str | None = "scoring/policy_de.json",
    profile: str = "paper_eval",
    out: str | Path = "build/eval/predictions.jsonl",
    summary: str | Path = "build/eval/summary.csv",
) -> dict[str, Any]:
    cases = load_cases(data)
    predictions: list[dict[str, Any]] = []

    session: MoniSession | None = None
    if method != "baseline":
        session = _create_session(profile, policy)

    for case in cases:
        if method == "baseline":
            prediction = _predict_with_baseline(case)
        else:
            assert session is not None
            prediction = _predict_with_session(case, session, method)
        predictions.append(prediction)

    metrics = compute_all_metrics(cases, predictions)
    summary_row: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "data": str(data),
        "method": method,
        "policy": policy or "",
        "profile": profile,
        "num_cases": len(cases),
        **metrics,
    }

    _write_jsonl(out, predictions)
    _write_summary(summary, summary_row)
    return {"summary": summary_row, "predictions": predictions}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MoniBox HSC-RAG-DE evaluation.")
    parser.add_argument("--data", default=None)
    parser.add_argument(
        "--method",
        default="hsc-rag-de",
        choices=["baseline", "hsc-rag-manual", "hsc-rag-de", "ablation"],
    )
    parser.add_argument("--policy", default=None)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--profile-file", default="profiles/paper_eval.yaml")
    parser.add_argument(
        "--suite",
        choices=["clean", "robust", "ablation", "export_tables"],
        default="clean",
    )
    parser.add_argument("--output-dir", default="build/eval/clean")
    parser.add_argument("--out", default=None)
    parser.add_argument("--summary", default=None)
    args = parser.parse_args()

    profile = _profile_name(args.profile, args.profile_file)
    data = args.data or _default_data_for_suite(args.suite)
    policy = args.policy
    if policy is None:
        policy = (
            "scoring/policy_de.json"
            if args.method == "hsc-rag-de"
            else "scoring/policy_manual.json"
        )
    out = Path(args.out) if args.out else _default_out(args.output_dir, args.suite, args.method)
    summary = (
        Path(args.summary)
        if args.summary
        else _default_summary(args.output_dir, args.suite, args.method)
    )

    result = run_eval(
        data=data,
        method=args.method,
        policy=policy,
        profile=profile,
        out=out,
        summary=summary,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
