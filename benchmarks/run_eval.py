from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app.config import PROJECT_ROOT
from runtime.runtime_config import load_runtime_config


def _profile_name(profile: str | None, profile_file: str | None) -> str:
    if profile:
        return profile
    if profile_file:
        return Path(profile_file).stem
    return "paper_eval"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MoniBox paper evaluation.")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--profile-file", default="profiles/paper_eval.yaml")
    parser.add_argument(
        "--suite",
        choices=["clean", "robust", "ablation", "export_tables"],
        default="clean",
    )
    parser.add_argument("--output-dir", default="build/eval")
    args = parser.parse_args()

    profile = _profile_name(args.profile, args.profile_file)
    os.environ["RUNTIME_PROFILE"] = profile

    cfg = load_runtime_config(profile)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "suite": args.suite,
        "profile": profile,
        "llm_backend": cfg.llm_backend,
        "llm_temperature": cfg.llm_temperature,
        "llm_stream": cfg.llm_stream,
        "rewrite_enabled": cfg.rewrite_enabled,
        "trace_path": "build/eval/traces/paper_eval_trace.jsonl",
    }
    manifest_path = output_dir / f"{args.suite}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {manifest_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
