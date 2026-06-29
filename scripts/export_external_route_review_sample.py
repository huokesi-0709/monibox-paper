from __future__ import annotations

import csv
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = (
    ROOT / "benchmarks" / "data_v2" / "clean_dev.jsonl",
    ROOT / "benchmarks" / "data_v2" / "clean_test.jsonl",
)
OUT_DIR = ROOT / "build" / "eval" / "final_v2" / "external_route_review"
SEED = 20260629
SAMPLE_SIZE = 20

ROUTE_LABELS = {
    "respiratory_distress": "\u547c\u5438\u56f0\u96be",
    "severe_bleeding": "\u4e25\u91cd\u51fa\u8840",
    "trapped_or_crush": "\u53d7\u56f0/\u6324\u538b",
    "head_or_consciousness": "\u5934\u90e8/\u610f\u8bc6\u5f02\u5e38",
    "collapse_aftershock": "\u7ed3\u6784\u5371\u9669/\u4f59\u9707",
    "hypothermia": "\u5931\u6e29",
    "dehydration": "\u8131\u6c34/\u53e3\u6e34",
    "pain_or_injury": "\u75bc\u75db/\u5916\u4f24",
    "low_battery": "\u4f4e\u7535\u91cf/\u5b9a\u4f4d\u6c42\u6551",
    "panic": "\u6050\u614c",
    "out_of_scope": "\u57df\u5916/\u4fe1\u606f\u4e0d\u8db3",
}


def load_clean_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in DATA_FILES:
        split = "dev" if "dev" in path.name else "test"
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if not text:
                    continue
                row = json.loads(text)
                row["_source_file"] = str(path.relative_to(ROOT)).replace("\\", "/")
                row["_split"] = split
                rows.append(row)
    return rows


def export_sample() -> dict[str, Any]:
    rows = load_clean_rows()
    sample = random.Random(SEED).sample(rows, SAMPLE_SIZE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUT_DIR / "clean_20_route_review.csv"
    md_path = OUT_DIR / "clean_20_route_review.md"
    manifest_path = OUT_DIR / "clean_20_route_review_manifest.json"

    fieldnames = [
        "review_no",
        "case_id",
        "split",
        "query",
        "expected_route",
        "expected_route_zh",
        "is_route_reasonable_yes_no_unclear",
        "reviewer_comment",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, row in enumerate(sample, start=1):
            route = str(row.get("expected_route") or "")
            writer.writerow(
                {
                    "review_no": index,
                    "case_id": row.get("id", ""),
                    "split": row.get("_split", ""),
                    "query": row.get("query", ""),
                    "expected_route": route,
                    "expected_route_zh": ROUTE_LABELS.get(route, ""),
                    "is_route_reasonable_yes_no_unclear": "",
                    "reviewer_comment": "",
                }
            )

    lines = [
        "# Clean Route Review Sample",
        "",
        f"- Generated at: {datetime.now(UTC).isoformat()}",
        f"- Random seed: {SEED}",
        "- Sampling frame: benchmarks/data_v2/clean_dev.jsonl + benchmarks/data_v2/clean_test.jsonl, n=1500",
        f"- Sample size: {SAMPLE_SIZE}",
        "",
        "## Reviewer Instructions",
        "",
        "\u8bf7\u8ba9\u4e00\u4f4d\u4e0d\u4e86\u89e3\u672c\u7cfb\u7edf\u7684\u4eba\u9605\u8bfb\u201c\u8f93\u5165\u6587\u672c\u201d\u548c\u201c\u671f\u671b\u8def\u7531\u201d\uff0c\u6309\u5e38\u8bc6\u5224\u65ad\u8fd9\u4e2a\u8def\u7531\u7c7b\u522b\u662f\u5426\u5408\u7406\u3002",
        "\u5efa\u8bae\u5728 `is_route_reasonable_yes_no_unclear` \u586b\uff1ayes / no / unclear\uff0c\u5e76\u5728 `reviewer_comment` \u5199\u4e00\u53e5\u7406\u7531\u3002",
        "",
        "## Route Labels",
        "",
        "| expected_route | \u4e2d\u6587\u91ca\u4e49 |",
        "|---|---|",
    ]
    for route, label in ROUTE_LABELS.items():
        lines.append(f"| {route} | {label} |")
    lines.extend(
        [
            "",
            "## Samples",
            "",
            "| # | case_id | split | \u8f93\u5165\u6587\u672c | expected_route | \u4e2d\u6587\u91ca\u4e49 | \u5224\u65ad | \u5907\u6ce8 |",
            "|---:|---|---|---|---|---|---|---|",
        ]
    )
    for index, row in enumerate(sample, start=1):
        route = str(row.get("expected_route") or "")
        query = str(row.get("query") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {index} | {row.get('id', '')} | {row.get('_split', '')} | "
            f"{query} | {route} | {ROUTE_LABELS.get(route, '')} |  |  |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "random_seed": SEED,
        "sampling_frame": [str(path.relative_to(ROOT)).replace("\\", "/") for path in DATA_FILES],
        "sampling_frame_count": len(rows),
        "sample_size": SAMPLE_SIZE,
        "csv": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
        "markdown": str(md_path.relative_to(ROOT)).replace("\\", "/"),
        "case_ids": [str(row.get("id") or "") for row in sample],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    print(json.dumps(export_sample(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
