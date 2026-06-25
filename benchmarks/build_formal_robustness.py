from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import PROJECT_ROOT
from benchmarks.schema import BenchmarkCase, load_cases


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _variant_query(query: str, variant: str) -> str:
    if variant == "filler_noise":
        return f"呃，{query}，请简短告诉我。"
    if variant == "long_context":
        return f"周围很乱，手机信号不稳定，{query} 我想先知道安全下一步。"
    if variant == "repetition":
        return f"我重复一遍，{query} {query}"
    msg = f"unknown robust variant: {variant}"
    raise ValueError(msg)


def build_robust_cases(clean_cases: list[BenchmarkCase]) -> list[BenchmarkCase]:
    robust: list[BenchmarkCase] = []
    variants = ("filler_noise", "long_context", "repetition")
    for clean in clean_cases:
        for index, variant in enumerate(variants, start=1):
            payload = clean.to_dict()
            payload.update(
                {
                    "id": f"{clean.id}_{variant}_{index:02d}",
                    "query": _variant_query(clean.query, variant),
                    "clean_id": clean.id,
                    "canonical_id": clean.canonical_id or clean.id,
                    "clean_query": clean.clean_query or clean.query,
                    "perturbation_type": variant,
                }
            )
            robust.append(BenchmarkCase.from_dict(payload))
    return robust


def write_cases(path: str | Path, cases: list[BenchmarkCase]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for case in cases:
            case.validate()
            f.write(json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True))
            f.write("\n")


def generate_formal_robustness(input_path: str | Path, output_path: str | Path) -> int:
    clean_cases = load_cases(input_path)
    robust_cases = build_robust_cases(clean_cases)
    write_cases(output_path, robust_cases)
    return len(robust_cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build formal robust benchmark JSONL.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    count = generate_formal_robustness(args.input, args.out)
    print(f"wrote {count} robust cases to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
