from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from benchmarks.ablations import ABLATION_NAMES, get_ablation_config
from benchmarks.baselines import (
    METHOD_CONFIGS,
    MethodConfig,
    baseline_reply,
    get_method_config,
)
from benchmarks.metrics import compute_all_metrics
from benchmarks.schema import BenchmarkCase, load_cases
from runtime.guard import GuardResult
from runtime.input_normalizer import InputNormalizer, NormalizedInput
from runtime.intent_extractor import IntentContext, IntentExtractor
from runtime.orchestrator import MoniSession, SessionConfig
from runtime.primitives import WorkingMemory
from runtime.protocol_matcher import ProtocolEngine, ProtocolMatchResult
from runtime.runtime_config import load_runtime_config
from runtime.scoring import HscRagPolicy, load_policy

VECTOR_ONLY_POLICY = HscRagPolicy(
    weights={
        "w_vec": 1.0,
        "w_sparse": 0.0,
        "w_quality": 0.0,
        "w_tag": 0.0,
        "w_risk": 0.0,
        "w_unsafe": 0.0,
        "w_redundancy": 0.0,
    },
    thresholds={},
    version="vector-only-no-safety-rerank",
)


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


class IdentityNormalizer:
    def normalize(self, raw_text: str) -> NormalizedInput:
        raw = "" if raw_text is None else str(raw_text)
        return NormalizedInput(
            raw_text=raw,
            canonical_text=raw.strip(),
            corrections=[],
            noise_removed=[],
            repeated_terms_collapsed=[],
        )


class DisabledIntentExtractor:
    def extract(self, text: str) -> IntentContext:
        return IntentContext(
            raw_text=text or "",
            clauses=[text] if text else [],
            primary_intent="out_of_scope",
            secondary_intents=[],
            risk_score=0.05,
            primary_risk_score=0.05,
            tags=["out_of_scope"],
            body_parts=[],
            scene_terms=[],
            negated_risks=[],
            matched_terms=[],
            explanation=["intent extraction disabled by benchmark method"],
        )


class NoNegationIntentExtractor:
    def __init__(self) -> None:
        self._inner = IntentExtractor()

    def extract(self, text: str) -> IntentContext:
        ctx = self._inner.extract(text)
        return IntentContext(
            raw_text=ctx.raw_text,
            clauses=ctx.clauses,
            primary_intent=ctx.primary_intent,
            secondary_intents=ctx.secondary_intents,
            risk_score=ctx.risk_score,
            primary_risk_score=ctx.primary_risk_score,
            tags=ctx.tags,
            body_parts=ctx.body_parts,
            scene_terms=ctx.scene_terms,
            negated_risks=[],
            matched_terms=ctx.matched_terms,
            explanation=[*ctx.explanation, "negation handling disabled by benchmark method"],
        )


class NoProtocolEngine:
    def match(self, text: str, routed_tags: list[str] | None = None, events: list[str] | None = None):
        del text, routed_tags, events
        return

    def match_with_score(
        self,
        text: str,
        routed_tags: list[str] | None = None,
        events: list[str] | None = None,
        intent_context: IntentContext | dict[str, Any] | None = None,
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
            reason=["protocol gate disabled by benchmark method"],
            protocol=None,
        )


class PassThroughGuard:
    def check(self, text: str) -> GuardResult:
        return GuardResult(level="allow", reasons=[], safe_text=text or "")


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


def _write_results_table(path: str | Path, summary: dict[str, Any]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


def _create_session(profile: str, config: MethodConfig, policy_path: str | None) -> MoniSession:
    os.environ["RUNTIME_PROFILE"] = profile
    cfg = load_runtime_config(profile)
    cfg.low_evidence_mode = config.use_low_evidence_routing
    cfg.rewrite_low_evidence_enabled = (
        cfg.rewrite_low_evidence_enabled and config.use_low_evidence_routing
    )

    guard = None if config.use_safety_guard else PassThroughGuard()
    protocol_engine = None if config.use_protocol_gate else NoProtocolEngine()
    input_normalizer = None if config.use_input_normalization else IdentityNormalizer()
    if not config.use_intent_extraction:
        intent_extractor = DisabledIntentExtractor()
    elif not config.use_negation_handling:
        intent_extractor = NoNegationIntentExtractor()
    else:
        intent_extractor = None

    session = MoniSession(
        str(PROJECT_ROOT / cfg.__dict__.get("rag_db_path", "build/rag.db")),
        SessionConfig(llm_path="", tts_enabled=bool(cfg.tts_backend)),
        safety_guard=guard,
        protocol_engine=protocol_engine,
        input_normalizer=input_normalizer,
        intent_extractor=intent_extractor,
        method_config=config,
    )
    session.rt.low_evidence_mode = config.use_low_evidence_routing
    if not config.use_safety_rerank and hasattr(session.rag, "hsc_policy"):
        session.rag.hsc_policy = VECTOR_ONLY_POLICY
    elif policy_path and hasattr(session.rag, "hsc_policy"):
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


def _predict_with_baseline(case: BenchmarkCase, config: MethodConfig) -> dict[str, Any]:
    normalizer = InputNormalizer() if config.use_input_normalization else IdentityNormalizer()
    if config.use_intent_extraction:
        intent_extractor = (
            IntentExtractor()
            if config.use_negation_handling
            else NoNegationIntentExtractor()
        )
    else:
        intent_extractor = DisabledIntentExtractor()
    protocol_engine = ProtocolEngine() if config.use_protocol_gate else NoProtocolEngine()

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
        "metadata": {
            "method": config.name,
            "disabled_modules": config.disabled_modules,
        },
    }
    return {
        "case": case.to_dict(),
        "case_id": case.id,
        "query": case.query,
        "method": config.name,
        "reply": reply,
        "trace": trace,
        "predicted_route": intent.primary_intent,
        "primary_intent": intent.primary_intent,
        "protocol_id": protocol.protocol_id,
        "latency_ms": 0.0,
    }


def _predict_with_session(
    case: BenchmarkCase, session: MoniSession, config: MethodConfig
) -> dict[str, Any]:
    _reset_session_for_case(session)
    reply = session.handle(case.query)
    trace = dict(session.last_trace)
    metadata = dict(trace.get("metadata") or {})
    metadata["method"] = config.name
    metadata["disabled_modules"] = config.disabled_modules
    trace["metadata"] = metadata
    return {
        "case": case.to_dict(),
        "case_id": case.id,
        "query": case.query,
        "method": config.name,
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
    policy: str | None = None,
    profile: str = "paper_eval",
    out: str | Path = "build/eval/predictions.jsonl",
    summary: str | Path = "build/eval/summary.csv",
    ablation: str | None = None,
) -> dict[str, Any]:
    cases = load_cases(data)
    predictions: list[dict[str, Any]] = []
    config = get_ablation_config(ablation) if ablation else get_method_config(method)
    if policy is not None:
        config = MethodConfig(
            name=config.name,
            use_input_normalization=config.use_input_normalization,
            use_intent_extraction=config.use_intent_extraction,
            use_negation_handling=config.use_negation_handling,
            use_protocol_gate=config.use_protocol_gate,
            use_safety_rerank=config.use_safety_rerank,
            use_low_evidence_routing=config.use_low_evidence_routing,
            use_safety_guard=config.use_safety_guard,
            policy_path=policy,
            llm_backend=config.llm_backend,
        )

    session: MoniSession | None = None
    if config.name not in {"baseline", "rule-only"}:
        session = _create_session(profile, config, config.policy_path)

    for case in cases:
        if config.name in {"baseline", "rule-only"}:
            prediction = _predict_with_baseline(case, config)
        else:
            assert session is not None
            prediction = _predict_with_session(case, session, config)
        predictions.append(prediction)

    metrics = compute_all_metrics(cases, predictions)
    summary_row: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "data": str(data),
        "method": config.name,
        "ablation": ablation or "",
        "policy": config.policy_path or "",
        "profile": profile,
        "disabled_modules": "|".join(config.disabled_modules),
        "num_cases": len(cases),
        **metrics,
    }

    _write_jsonl(out, predictions)
    _write_summary(summary, summary_row)
    results_name = "ablation_results.csv" if ablation else "main_results.csv"
    _write_results_table(_resolve(summary).parent / results_name, summary_row)
    return {"summary": summary_row, "predictions": predictions}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MoniBox HSC-RAG-DE evaluation.")
    parser.add_argument("--data", default=None)
    parser.add_argument(
        "--method",
        default="hsc-rag-de",
        choices=sorted(METHOD_CONFIGS),
    )
    parser.add_argument("--ablation", default=None, choices=sorted(ABLATION_NAMES))
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
    config = get_ablation_config(args.ablation) if args.ablation else get_method_config(args.method)
    policy = args.policy if args.policy is not None else config.policy_path
    run_name = args.ablation or args.method
    out = Path(args.out) if args.out else _default_out(args.output_dir, args.suite, run_name)
    summary = (
        Path(args.summary)
        if args.summary
        else _default_summary(args.output_dir, args.suite, run_name)
    )

    result = run_eval(
        data=data,
        method=args.method,
        policy=policy,
        profile=profile,
        out=out,
        summary=summary,
        ablation=args.ablation,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
