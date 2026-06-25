from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.config import PROJECT_ROOT


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def split_sheet(input_path: str | Path, output_dir: str | Path, batch_size: int = 50) -> int:
    source = _resolve(input_path)
    out_dir = _resolve(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if batch_size <= 0:
        msg = "batch_size must be positive"
        raise ValueError(msg)
    count = 0
    stem = source.stem
    for start in range(0, len(rows), batch_size):
        count += 1
        batch = rows[start : start + batch_size]
        out = out_dir / f"{stem}_batch_{count:02d}.csv"
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(batch)
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split annotation CSV into batches.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args(argv)

    count = split_sheet(args.input, args.output_dir, args.batch_size)
    print(f"wrote {count} batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
