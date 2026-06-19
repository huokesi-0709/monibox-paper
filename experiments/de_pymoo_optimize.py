from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime

from app.config import PROJECT_ROOT
from runtime.runtime_config import load_runtime_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run offline DE weight optimization for HSC-RAG paper experiments."
    )
    parser.add_argument("--profile", default="paper_eval")
    parser.add_argument("--profile-file", default="profiles/paper_eval.yaml")
    parser.add_argument("--output-dir", default="build/eval/de")
    parser.add_argument("--seed", type=int, default=20260618)
    args = parser.parse_args()

    del args.profile_file
    os.environ["RUNTIME_PROFILE"] = args.profile
    cfg = load_runtime_config(args.profile)

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "profile": args.profile,
        "seed": args.seed,
        "optimizer": "pymoo.DifferentialEvolution",
        "llm_backend": cfg.llm_backend,
        "status": "configured",
    }
    manifest_path = output_dir / "de_optimize_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {manifest_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
