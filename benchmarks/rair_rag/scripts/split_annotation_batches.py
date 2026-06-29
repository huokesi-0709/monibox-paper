from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROUND_DIR = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "annotation_rounds"
)
DEFAULT_INPUT = ROUND_DIR / "round1_for_annotation.csv"
DEFAULT_OUT_A = ROUND_DIR / "round1_annotator_A.csv"
DEFAULT_OUT_B = ROUND_DIR / "round1_annotator_B.csv"

ANNOTATION_FIELDS = [
    "human_accept",
    "annotator_primary_intent",
    "annotator_secondary_intents",
    "annotator_negated_risks",
    "annotator_operational_constraints",
    "annotator_should_not_trigger",
    "annotator_notes",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split RAIR-RAG annotation CSV into independent A/B batches."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-a", type=Path, default=DEFAULT_OUT_A)
    parser.add_argument("--out-b", type=Path, default=DEFAULT_OUT_B)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = split_annotation_batches(
        input_path=args.input,
        out_a=args.out_a,
        out_b=args.out_b,
        sample_size=args.sample_size,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(result)


def split_annotation_batches(
    *,
    input_path: Path,
    out_a: Path,
    out_b: Path,
    sample_size: int | None,
    seed: int,
    overwrite: bool,
) -> dict[str, int | str | None]:
    ensure_outputs_available([out_a, out_b], overwrite=overwrite)
    rows, fieldnames = read_csv(input_path)
    selected_rows = sample_rows(rows, sample_size=sample_size, seed=seed)
    output_fields = output_fieldnames(fieldnames)
    write_csv(out_a, output_fields, build_rows(selected_rows, annotator_id="A"))
    write_csv(out_b, output_fields, build_rows(selected_rows, annotator_id="B"))
    return {
        "input": str(input_path),
        "rows_in": len(rows),
        "rows_out_A": len(selected_rows),
        "rows_out_B": len(selected_rows),
        "sample_size": sample_size,
        "seed": seed,
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


def sample_rows(
    rows: list[dict[str, str]], *, sample_size: int | None, seed: int
) -> list[dict[str, str]]:
    if sample_size is None:
        return rows
    if sample_size < 1:
        raise ValueError("--sample-size must be positive")
    if sample_size > len(rows):
        raise ValueError(
            f"--sample-size {sample_size} exceeds available rows {len(rows)}"
        )
    rng = random.Random(seed)  # noqa: S311 - deterministic sampling for annotation.
    indexes = sorted(rng.sample(range(len(rows)), sample_size))
    return [rows[index] for index in indexes]


def output_fieldnames(fieldnames: list[str]) -> list[str]:
    output = list(fieldnames)
    if "annotator_id" not in output:
        insert_at = output.index("id") + 1 if "id" in output else 0
        output.insert(insert_at, "annotator_id")
    for field_name in ANNOTATION_FIELDS:
        if field_name not in output:
            output.append(field_name)
    return output


def build_rows(rows: list[dict[str, str]], *, annotator_id: str) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        item["annotator_id"] = annotator_id
        for field_name in ANNOTATION_FIELDS:
            item[field_name] = ""
        output.append(item)
    return output


def write_csv(
    path: Path, fieldnames: list[str], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
