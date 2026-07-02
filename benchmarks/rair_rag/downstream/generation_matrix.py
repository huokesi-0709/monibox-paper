from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from app.config import settings
from benchmarks.rair_rag.downstream.generation_eval import run_generation_eval
from benchmarks.rair_rag.downstream.llm_clients import (
    DEFAULT_LOCAL_MODEL_PATH,
    DEFAULT_REFERENCE_BASE_URL,
    DEFAULT_REFERENCE_MODEL,
    DEFAULT_REFERENCE_PROVIDER,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
)
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"
SUPPORTED_GENERATORS = ("local-llm", "reference-llm")
SUPPORTED_SYSTEMS = ("vanilla-rag", "rair-rag")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full downstream generation matrix with uv."
    )
    parser.add_argument("--generator", choices=SUPPORTED_GENERATORS, required=True)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--rag-db", type=Path, default=_default_rag_db_path())
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--include-extension", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--sleep-between-calls", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--case-start", type=int)
    parser.add_argument("--case-end", type=int)
    args = parser.parse_args()

    out_dir = args.out_dir or _default_out_dir(args.generator)
    try:
        summary = run_generation_matrix(
            generator_name=args.generator,
            data_path=args.data,
            rag_db_path=args.rag_db,
            topk=args.topk,
            out_dir=out_dir,
            max_cases=args.max_cases,
            include_extension=args.include_extension,
            resume=args.resume,
            skip_existing=args.skip_existing,
            overwrite=args.overwrite,
            sleep_between_calls=args.sleep_between_calls,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            case_start=args.case_start,
            case_end=args.case_end,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def run_generation_matrix(
    *,
    generator_name: str,
    data_path: Path,
    rag_db_path: Path,
    topk: int,
    out_dir: Path,
    max_cases: int | None = None,
    include_extension: bool = False,
    resume: bool = False,
    skip_existing: bool = False,
    overwrite: bool = False,
    sleep_between_calls: float = 0.0,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    case_start: int | None = None,
    case_end: int | None = None,
) -> dict[str, Any]:
    if generator_name not in SUPPORTED_GENERATORS:
        allowed = ", ".join(SUPPORTED_GENERATORS)
        msg = f"unsupported generator {generator_name}; choose one of {allowed}"
        raise ValueError(msg)
    if topk <= 0:
        raise ValueError("--topk must be a positive integer")
    if max_cases is not None and max_cases <= 0:
        raise ValueError("--max-cases must be a positive integer when provided")
    if sleep_between_calls < 0:
        raise ValueError("--sleep-between-calls must be non-negative")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive when provided")
    if max_retries is not None and max_retries < 0:
        raise ValueError("--max-retries must be non-negative when provided")
    if overwrite and (resume or skip_existing):
        raise ValueError("--overwrite cannot be combined with --resume or --skip-existing")
    if case_start is not None and case_start < 0:
        raise ValueError("--case-start must be non-negative when provided")
    if case_end is not None and case_end < 0:
        raise ValueError("--case-end must be non-negative when provided")
    if case_start is not None and case_end is not None and case_end < case_start:
        raise ValueError("--case-end must be greater than or equal to --case-start")
    _validate_environment(
        generator_name,
        require_reference_api_key=not (resume or skip_existing),
    )
    if not rag_db_path.exists():
        msg = (
            f"RAG database not found: {rag_db_path}. "
            "Please run `uv run monibox-build-rag` first, or set RAG_DB_PATH."
        )
        raise FileNotFoundError(msg)

    out_dir.mkdir(parents=True, exist_ok=True)
    datasets = [("rair_test", data_path)]
    if include_extension:
        datasets.append(
            (
                "rair_test_multi_intent_negation",
                PROJECT_ROOT
                / "benchmarks"
                / "rair_rag"
                / "data"
                / "test"
                / "rair_test_multi_intent_negation.jsonl",
            )
        )

    runs: list[dict[str, Any]] = []
    for dataset_name, dataset_path in datasets:
        for system_name in SUPPORTED_SYSTEMS:
            out_path = out_dir / (
                f"{dataset_name}_{system_name}_{generator_name}_outputs.jsonl"
            )
            summary_path = out_dir / (
                f"{dataset_name}_{system_name}_{generator_name}_summary.json"
            )
            summary = run_generation_eval(
                data_path=dataset_path,
                system_name=system_name,
                generator_name=generator_name,
                rag_db_path=rag_db_path,
                topk=topk,
                out_path=out_path,
                summary_path=summary_path,
                max_cases=max_cases,
                resume=resume,
                skip_existing=skip_existing,
                overwrite=overwrite,
                sleep_between_calls=sleep_between_calls,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                case_start=case_start,
                case_end=case_end,
            )
            runs.append(summary)

    manifest = {
        "generator": generator_name,
        "model": (
            os.getenv("REFERENCE_LLM_MODEL")
            if generator_name == "reference-llm"
            else os.getenv("LOCAL_LLM_MODEL_PATH")
            or "models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf"
        ),
        "provider": (
            os.getenv("REFERENCE_LLM_PROVIDER")
            if generator_name == "reference-llm"
            else "local-llm"
        ),
        "base_url": (
            os.getenv("REFERENCE_LLM_BASE_URL")
            if generator_name == "reference-llm"
            else None
        ),
        "data": str(data_path),
        "systems": list(SUPPORTED_SYSTEMS),
        "topk": topk,
        "resume": resume,
        "skip_existing": skip_existing,
        "overwrite": overwrite,
        "case_start": case_start,
        "case_end": case_end,
        "max_cases": max_cases,
        "created_from_existing_outputs": any(
            int(run.get("num_skipped_existing") or 0) > 0 for run in runs
        ),
        "resumable": True,
        "runs": [
            {
                "system": run.get("system"),
                "output": run.get("output"),
                "num_outputs": run.get("num_outputs"),
                "num_skipped_existing": run.get("num_skipped_existing"),
                "num_generated": run.get("num_generated"),
                "num_failures": run.get("num_failures"),
                "resume": run.get("resume"),
                "skip_existing": run.get("skip_existing"),
                "overwrite": run.get("overwrite"),
                "latency_summary": run.get("latency_summary"),
            }
            for run in runs
        ],
        "note": (
            "The output files are written incrementally and can be resumed safely. "
            "This manifest records the runtime configuration for the completed run."
        ),
    }
    write_json(
        out_dir
        / (
            "reference_generation_manifest.json"
            if generator_name == "reference-llm"
            else "local_generation_manifest.json"
        ),
        manifest,
    )

    return {
        "generator": generator_name,
        "data": str(data_path),
        "rag_db": str(rag_db_path),
        "topk": topk,
        "out_dir": str(out_dir),
        "max_cases": max_cases,
        "include_extension": include_extension,
        "resume": resume,
        "skip_existing": skip_existing,
        "overwrite": overwrite,
        "sleep_between_calls": sleep_between_calls,
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
        "case_start": case_start,
        "case_end": case_end,
        "runs": runs,
    }


def _validate_environment(
    generator_name: str, *, require_reference_api_key: bool = True
) -> None:
    if generator_name == "local-llm":
        model_path = Path(os.getenv("LOCAL_LLM_MODEL_PATH") or DEFAULT_LOCAL_MODEL_PATH)
        if not model_path.is_absolute():
            model_path = (PROJECT_ROOT / model_path).resolve()
        if not model_path.exists():
            raise FileNotFoundError(
                f"Local GGUF model file not found: {model_path}. "
                "Place Qwen1.5-0.5B-Chat-Q4_K_M at "
                "models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf, or set "
                "LOCAL_LLM_MODEL_PATH to the correct GGUF path."
            )
        return
    if require_reference_api_key and not os.getenv("REFERENCE_LLM_API_KEY"):
        raise RuntimeError(
            "REFERENCE_LLM_API_KEY is not set. Export it in your shell or put it in "
            ".env before running the reference generator."
        )
    if not os.getenv("REFERENCE_LLM_BASE_URL"):
        os.environ["REFERENCE_LLM_BASE_URL"] = DEFAULT_REFERENCE_BASE_URL
    if not os.getenv("REFERENCE_LLM_PROVIDER"):
        os.environ["REFERENCE_LLM_PROVIDER"] = DEFAULT_REFERENCE_PROVIDER
    if not os.getenv("REFERENCE_LLM_MODEL"):
        os.environ["REFERENCE_LLM_MODEL"] = DEFAULT_REFERENCE_MODEL


def _default_rag_db_path() -> Path:
    return Path(os.getenv("RAG_DB_PATH") or settings.rag_db_path)


def _default_out_dir(generator_name: str) -> Path:
    return DEFAULT_OUT_DIR / generator_name.replace("-llm", "")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
