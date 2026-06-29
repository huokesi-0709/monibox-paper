from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROUND_DIR = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "annotation_rounds"
)
DEFAULT_BASE = ROUND_DIR / "round1_for_annotation.csv"
DEFAULT_SUGGESTIONS = ROUND_DIR / "round1_screening_suggestions.csv"
DEFAULT_MERGED = ROUND_DIR / "round1_merged.csv"
DEFAULT_ANNOTATOR_A = ROUND_DIR / "round1_for_annotator_A.csv"
DEFAULT_ANNOTATOR_B = ROUND_DIR / "round1_for_annotator_B.csv"
DEFAULT_REWRITE_QUEUE = ROUND_DIR / "round1_rewrite_queue.csv"
DEFAULT_ADJUDICATION_QUEUE = ROUND_DIR / "round1_needs_adjudication.csv"

SCREENING_FIELDS = [
    "human_accept",
    "human_notes",
    "annotator_primary_intent",
    "annotator_negated_risks",
    "annotator_secondary_intents",
]

ANNOTATOR_BLANK_FIELDS = [
    "human_accept",
    "human_notes",
    "annotator_primary_intent",
    "annotator_negated_risks",
    "annotator_secondary_intents",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge RAIR-RAG round-1 screening suggestions by id."
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--suggestions", type=Path, default=DEFAULT_SUGGESTIONS)
    parser.add_argument("--merged", type=Path, default=DEFAULT_MERGED)
    parser.add_argument("--annotator-a", type=Path, default=DEFAULT_ANNOTATOR_A)
    parser.add_argument("--annotator-b", type=Path, default=DEFAULT_ANNOTATOR_B)
    parser.add_argument("--rewrite-queue", type=Path, default=DEFAULT_REWRITE_QUEUE)
    parser.add_argument(
        "--adjudication-queue", type=Path, default=DEFAULT_ADJUDICATION_QUEUE
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = merge_screening_suggestions(
        base_path=args.base,
        suggestions_path=args.suggestions,
        merged_path=args.merged,
        annotator_a_path=args.annotator_a,
        annotator_b_path=args.annotator_b,
        rewrite_queue_path=args.rewrite_queue,
        adjudication_queue_path=args.adjudication_queue,
        overwrite=args.overwrite,
    )
    print(result)


def merge_screening_suggestions(
    *,
    base_path: Path,
    suggestions_path: Path,
    merged_path: Path,
    annotator_a_path: Path,
    annotator_b_path: Path,
    rewrite_queue_path: Path,
    adjudication_queue_path: Path,
    overwrite: bool,
) -> dict[str, int]:
    ensure_outputs_available(
        [
            merged_path,
            annotator_a_path,
            annotator_b_path,
            rewrite_queue_path,
            adjudication_queue_path,
        ],
        overwrite=overwrite,
    )
    base_rows, fieldnames = read_csv(base_path)
    suggestion_rows, _suggestion_fields = read_csv(suggestions_path)
    suggestions_by_id = index_by_id(suggestion_rows, suggestions_path)

    merged_rows: list[dict[str, str]] = []
    for row in base_rows:
        item_id = row["id"]
        if item_id not in suggestions_by_id:
            raise ValueError(f"{suggestions_path}: missing suggestion for id {item_id}")
        merged = dict(row)
        suggestion = suggestions_by_id[item_id]
        for field_name in SCREENING_FIELDS:
            merged[field_name] = suggestion.get(field_name, "")
        merged_rows.append(merged)

    extra_ids = set(suggestions_by_id) - {row["id"] for row in base_rows}
    if extra_ids:
        sample = ", ".join(sorted(extra_ids)[:5])
        raise ValueError(f"{suggestions_path}: suggestions contain unknown ids: {sample}")

    accepted = [row for row in merged_rows if row["human_accept"] == "yes"]
    rewrite = [row for row in merged_rows if row["human_accept"] == "rewrite"]
    adjudication = [
        row for row in merged_rows if row["human_accept"] == "needs_adjudication"
    ]
    unsupported = [
        row["id"]
        for row in merged_rows
        if row["human_accept"] not in {"yes", "no", "rewrite", "needs_adjudication"}
    ]
    if unsupported:
        raise ValueError(f"unsupported human_accept values for ids: {unsupported[:5]}")

    write_csv(merged_path, fieldnames, merged_rows)
    write_csv(annotator_a_path, fieldnames, blank_annotator_fields(accepted))
    write_csv(annotator_b_path, fieldnames, blank_annotator_fields(accepted))
    write_csv(rewrite_queue_path, fieldnames, rewrite)
    write_csv(adjudication_queue_path, fieldnames, adjudication)

    counts = Counter(row["human_accept"] for row in merged_rows)
    return {
        "merged": len(merged_rows),
        "annotator_A": len(accepted),
        "annotator_B": len(accepted),
        "rewrite_queue": len(rewrite),
        "adjudication_queue": len(adjudication),
        "yes": counts["yes"],
        "no": counts["no"],
        "rewrite": counts["rewrite"],
        "needs_adjudication": counts["needs_adjudication"],
    }


def ensure_outputs_available(paths: list[Path], *, overwrite: bool) -> None:
    if overwrite:
        return
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"output already exists; pass --overwrite: {joined}")


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if "id" not in fieldnames:
        raise ValueError(f"{path}: missing id column")
    return rows, fieldnames


def index_by_id(rows: list[dict[str, str]], path: Path) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        item_id = row.get("id", "")
        if not item_id:
            raise ValueError(f"{path}: row missing id")
        if item_id in indexed:
            raise ValueError(f"{path}: duplicate id {item_id}")
        indexed[item_id] = row
    return indexed


def blank_annotator_fields(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    blanked: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        for field_name in ANNOTATOR_BLANK_FIELDS:
            item[field_name] = ""
        blanked.append(item)
    return blanked


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
