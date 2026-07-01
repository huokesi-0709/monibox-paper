from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from app.config import settings
from benchmarks.rair_rag.downstream.generation_eval import run_generation_eval
from benchmarks.rair_rag.downstream.llm_clients import DEFAULT_LOCAL_MODEL_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
)
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "downstream_eval" / "generation"
DEFAULT_REFERENCE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
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
    args = parser.parse_args()

    out_dir = args.out_dir or _default_out_dir(args.generator)
    summary = run_generation_matrix(
        generator_name=args.generator,
        data_path=args.data,
        rag_db_path=args.rag_db,
        topk=args.topk,
        out_dir=out_dir,
        max_cases=args.max_cases,
        include_extension=args.include_extension,
    )
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
) -> dict[str, Any]:
    if generator_name not in SUPPORTED_GENERATORS:
        allowed = ", ".join(SUPPORTED_GENERATORS)
        msg = f"unsupported generator {generator_name}; choose one of {allowed}"
        raise ValueError(msg)
    if topk <= 0:
        raise ValueError("--topk must be a positive integer")
    if max_cases is not None and max_cases <= 0:
        raise ValueError("--max-cases must be a positive integer when provided")
    _validate_environment(generator_name)
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
            )
            runs.append(summary)

    return {
        "generator": generator_name,
        "data": str(data_path),
        "rag_db": str(rag_db_path),
        "topk": topk,
        "out_dir": str(out_dir),
        "max_cases": max_cases,
        "include_extension": include_extension,
        "runs": runs,
    }


def _validate_environment(generator_name: str) -> None:
    if generator_name == "local-llm":
        model_path = Path(os.getenv("LOCAL_LLM_MODEL_PATH") or DEFAULT_LOCAL_MODEL_PATH)
        if not model_path.is_absolute():
            model_path = (PROJECT_ROOT / model_path).resolve()
        if not model_path.exists():
            raise FileNotFoundError(
                f"Local GGUF model file not found: {model_path}. "
                "Place the model under models/llm/ or set LOCAL_LLM_MODEL_PATH."
            )
        return
    if not os.getenv("REFERENCE_LLM_API_KEY"):
        raise RuntimeError(
            "REFERENCE_LLM_API_KEY is not set. Export it in your shell or put it in "
            ".env before running the reference generator."
        )
    if not os.getenv("REFERENCE_LLM_BASE_URL"):
        os.environ["REFERENCE_LLM_BASE_URL"] = DEFAULT_REFERENCE_BASE_URL
    if not os.getenv("REFERENCE_LLM_MODEL"):
        os.environ["REFERENCE_LLM_MODEL"] = "qwen2.5-7b-instruct"


def _default_rag_db_path() -> Path:
    return Path(os.getenv("RAG_DB_PATH") or settings.rag_db_path)


def _default_out_dir(generator_name: str) -> Path:
    return DEFAULT_OUT_DIR / generator_name.replace("-llm", "")


if __name__ == "__main__":
    main()
