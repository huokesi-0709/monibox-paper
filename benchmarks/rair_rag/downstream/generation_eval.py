from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.config import settings
from benchmarks.rair_rag.downstream.llm_clients import (
    BaseGenerator,
    LocalLlamaCppGenerator,
    ReferenceApiGenerator,
)
from benchmarks.rair_rag.downstream.prompt_builders import (
    build_rair_generation_prompt,
    build_vanilla_generation_prompt,
)
from benchmarks.rair_rag.downstream.retrieval_eval import load_downstream_cases
from benchmarks.rair_rag.downstream.schema import DownstreamCase, RetrievedEvidence
from benchmarks.rair_rag.downstream.systems import (
    DownstreamSystem,
    RairRagSystem,
    VanillaRagSystem,
)
from runtime.rag_engine import RagEngine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
)
DEFAULT_GENERATION_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"
SUPPORTED_SYSTEMS = {"vanilla-rag": VanillaRagSystem, "rair-rag": RairRagSystem}
SUPPORTED_GENERATORS = {"local-llm", "reference-llm"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run downstream generation evaluation with local or reference generators."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--system", choices=sorted(SUPPORTED_SYSTEMS), required=True)
    parser.add_argument(
        "--generator", choices=sorted(SUPPORTED_GENERATORS), required=True
    )
    parser.add_argument("--rag-db", type=Path, default=_default_rag_db_path())
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--max-cases", type=int)
    args = parser.parse_args()

    out_path = args.out or _default_out_path(args.data, args.system, args.generator)
    summary_path = args.summary or _default_summary_path(
        args.data, args.system, args.generator
    )
    try:
        summary = run_generation_eval(
            data_path=args.data,
            system_name=args.system,
            generator_name=args.generator,
            rag_db_path=args.rag_db,
            topk=args.topk,
            out_path=out_path,
            summary_path=summary_path,
            max_cases=args.max_cases,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_generation_eval(
    *,
    data_path: Path,
    system_name: str,
    generator_name: str,
    rag_db_path: Path,
    topk: int,
    out_path: Path,
    summary_path: Path,
    max_cases: int | None = None,
    generator: BaseGenerator | None = None,
) -> dict[str, Any]:
    if topk <= 0:
        msg = "--topk must be a positive integer"
        raise ValueError(msg)
    if max_cases is not None and max_cases <= 0:
        msg = "--max-cases must be a positive integer when provided"
        raise ValueError(msg)
    if system_name not in SUPPORTED_SYSTEMS:
        allowed = ", ".join(sorted(SUPPORTED_SYSTEMS))
        msg = f"unsupported system {system_name}; choose one of {allowed}"
        raise ValueError(msg)
    if generator_name not in SUPPORTED_GENERATORS:
        allowed = ", ".join(sorted(SUPPORTED_GENERATORS))
        msg = f"unsupported generator {generator_name}; choose one of {allowed}"
        raise ValueError(msg)
    if not rag_db_path.exists():
        msg = (
            f"RAG database not found: {rag_db_path}. "
            "Please run `uv run monibox-build-rag` first, or pass --rag-db / set "
            "RAG_DB_PATH to an existing rag.db file."
        )
        raise FileNotFoundError(msg)

    cases = load_downstream_cases(data_path)
    if max_cases is not None:
        cases = cases[:max_cases]

    system = SUPPORTED_SYSTEMS[system_name]()
    rag_engine = RagEngine(str(rag_db_path))
    active_generator = generator or build_generator(generator_name)
    outputs = [
        generate_case(
            case=case,
            system=system,
            generator=active_generator,
            generator_name=generator_name,
            rag_engine=rag_engine,
            topk=topk,
        )
        for case in cases
    ]
    summary = {
        "data": str(data_path),
        "system": system_name,
        "generator": generator_name,
        "rag_db": str(rag_db_path),
        "topk": topk,
        "max_cases": max_cases,
        "num_cases": len(cases),
        "num_outputs": len(outputs),
        "output": str(out_path),
    }
    write_jsonl(out_path, outputs)
    write_json(summary_path, summary)
    return summary


def generate_case(
    *,
    case: DownstreamCase,
    system: DownstreamSystem,
    generator: BaseGenerator,
    generator_name: str,
    rag_engine: RagEngine,
    topk: int,
) -> dict[str, Any]:
    evidence = system.retrieve(case=case, rag_engine=rag_engine, topk=topk)
    trace = dict(system.last_trace)
    risk_context = _dict_value(trace.get("risk_context"))
    prompt = build_generation_prompt(
        case=case, system_name=system.name, risk_context=risk_context, evidence=evidence
    )
    raw_output = generator.generate(prompt)
    parsed_output = parse_generation_output(raw_output)
    return {
        "id": case.id,
        "system": system.name,
        "generator": generator_name,
        "raw_input": case.raw_input,
        "case": case.to_dict(),
        "prompt_hash": prompt_hash(prompt),
        "prompt": prompt,
        "raw_output": raw_output,
        "parsed_output": parsed_output,
        "risk_context": risk_context,
        "retrieved_evidence": [item.to_dict() for item in evidence],
        "predicted_protocol_id": parsed_output.get("protocol_id"),
        "trace": {
            **trace,
            "prompt_builder": system.name,
            "topk": topk,
            "parse_ok": bool(parsed_output.get("_parse_ok")),
        },
    }


def build_generation_prompt(
    *,
    case: DownstreamCase,
    system_name: str,
    risk_context: dict[str, Any],
    evidence: list[RetrievedEvidence],
) -> str:
    if system_name == "vanilla-rag":
        return build_vanilla_generation_prompt(case, evidence)
    if system_name == "rair-rag":
        return build_rair_generation_prompt(case, risk_context, evidence)
    msg = f"unsupported generation system: {system_name}"
    raise ValueError(msg)


def build_generator(generator_name: str) -> BaseGenerator:
    if generator_name == "local-llm":
        return LocalLlamaCppGenerator()
    if generator_name == "reference-llm":
        return ReferenceApiGenerator()
    msg = f"unsupported generator: {generator_name}"
    raise ValueError(msg)


def parse_generation_output(raw_output: str) -> dict[str, Any]:
    text = str(raw_output or "").strip()
    if not text:
        return {
            "protocol_id": None,
            "reply": "",
            "safety_notes": [],
            "used_evidence": [],
            "_parse_ok": False,
            "_parse_error": "empty output",
        }
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fallback_parsed_output(text, f"invalid JSON: {exc}")
    if not isinstance(payload, dict):
        return _fallback_parsed_output(text, "JSON output is not an object")
    return {
        "protocol_id": payload.get("protocol_id"),
        "reply": str(payload.get("reply") or ""),
        "safety_notes": _list_value(payload.get("safety_notes")),
        "used_evidence": _list_value(payload.get("used_evidence")),
        "_parse_ok": True,
    }


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


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


def _fallback_parsed_output(raw_text: str, error: str) -> dict[str, Any]:
    return {
        "protocol_id": None,
        "reply": raw_text,
        "safety_notes": [],
        "used_evidence": [],
        "_parse_ok": False,
        "_parse_error": error,
    }


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _default_rag_db_path() -> Path:
    return Path(os.getenv("RAG_DB_PATH") or settings.rag_db_path)


def _default_out_path(data_path: Path, system_name: str, generator_name: str) -> Path:
    out_dir = DEFAULT_GENERATION_DIR / generator_name.replace("-llm", "")
    return out_dir / f"{data_path.stem}_{system_name}_{generator_name}_outputs.jsonl"


def _default_summary_path(
    data_path: Path, system_name: str, generator_name: str
) -> Path:
    out_dir = DEFAULT_GENERATION_DIR / generator_name.replace("-llm", "")
    return out_dir / f"{data_path.stem}_{system_name}_{generator_name}_summary.json"


if __name__ == "__main__":
    main()
