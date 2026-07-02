from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GENERATION_DIR = (
    PROJECT_ROOT / "build" / "downstream_eval" / "generation" / "reference"
)
DEFAULT_OUT = DEFAULT_GENERATION_DIR / "reference_generation_manifest.json"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LEGACY_MODEL_MARKERS = (
    "".join(("Qwen", "2.5", "-7B-Instruct")),
    "".join(("qwen", "2.5", "-7b-instruct")),
    "".join(("Qwen", "2.5")),
    "".join(("qwen", "2.5")),
)
SYSTEM_ORDER = ("vanilla-rag", "rair-rag")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a manifest for completed reference-llm generation outputs "
            "without modifying the original JSONL files."
        )
    )
    parser.add_argument("--generation-dir", type=Path, default=DEFAULT_GENERATION_DIR)
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--provider", default="dashscope_openai")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    manifest = create_reference_manifest(
        generation_dir=args.generation_dir,
        model=args.model,
        provider=args.provider,
        base_url=args.base_url,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.out), **manifest}, ensure_ascii=False))


def create_reference_manifest(
    *,
    generation_dir: Path,
    model: str,
    provider: str,
    base_url: str,
) -> dict[str, Any]:
    output_paths = sorted(generation_dir.glob("*_outputs.jsonl"))
    summary_paths = sorted(generation_dir.glob("*_summary.json"))
    reference_outputs = _reference_file_names(output_paths)
    reference_summaries = _reference_file_names(summary_paths)

    return {
        "generator": "reference-llm",
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "setting": "strong_hosted_reference",
        "outputs": reference_outputs,
        "summaries": reference_summaries,
        "created_from_existing_outputs": True,
        "warnings": _legacy_model_warnings([*output_paths, *summary_paths]),
        "note": (
            "Original outputs were generated before model metadata was written "
            "into each row."
        ),
    }


def _reference_file_names(paths: list[Path]) -> list[str]:
    names = [path.name for path in paths if "reference-llm" in path.name]
    return sorted(names, key=_manifest_name_sort_key)


def _manifest_name_sort_key(name: str) -> tuple[int, str]:
    for index, system in enumerate(SYSTEM_ORDER):
        if f"_{system}_" in name:
            return index, name
    return len(SYSTEM_ORDER), name


def _legacy_model_warnings(paths: list[Path]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for path in paths:
        name_marker = _first_legacy_marker(path.name)
        if name_marker:
            warnings.append(
                {
                    "path": str(path),
                    "where": "filename",
                    "marker": name_marker,
                }
            )
        content_marker = _first_legacy_marker_in_file(path)
        if content_marker:
            warnings.append(
                {
                    "path": str(path),
                    "where": "content",
                    "marker": content_marker,
                }
            )
    return warnings


def _first_legacy_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in LEGACY_MODEL_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def _first_legacy_marker_in_file(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                marker = _first_legacy_marker(line)
                if marker:
                    return marker
    except UnicodeDecodeError:
        return "unreadable_non_utf8_file"
    return None


if __name__ == "__main__":
    main()
