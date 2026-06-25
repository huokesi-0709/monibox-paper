from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.config import PROJECT_ROOT


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def merge_batches(input_dir: str | Path, output_path: str | Path) -> int:
    source_dir = _resolve(input_dir)
    batch_paths = sorted(source_dir.glob("*.csv"))
    if not batch_paths:
        msg = f"no CSV batches found in {source_dir}"
        raise ValueError(msg)

    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    seen_ids: set[str] = set()
    for path in batch_paths:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            current_fields = list(reader.fieldnames or [])
            if fieldnames is None:
                fieldnames = current_fields
            elif current_fields != fieldnames:
                msg = f"{path} headers differ from previous batches"
                raise ValueError(msg)
            for row in reader:
                case_id = (row.get("case_id") or "").strip()
                if not case_id:
                    msg = f"{path} contains a row without case_id"
                    raise ValueError(msg)
                if case_id in seen_ids:
                    msg = f"duplicate case_id across batches: {case_id}"
                    raise ValueError(msg)
                seen_ids.add(case_id)
                rows.append(row)

    output = _resolve(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge annotation CSV batches.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    count = merge_batches(args.input_dir, args.out)
    print(f"merged {count} rows into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
