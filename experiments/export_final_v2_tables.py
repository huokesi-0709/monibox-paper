from __future__ import annotations

import json

from experiments.export_paper_tables import export_paper_tables
from experiments.export_tables import export_tables
from experiments.final_v2_utils import FINAL_V2_DIR


def main() -> int:
    tables_dir = FINAL_V2_DIR / "tables"
    generic_report = export_tables(FINAL_V2_DIR, tables_dir / "generic")
    paper_report = export_paper_tables(FINAL_V2_DIR, tables_dir)
    report = {
        "eval_dir": str(FINAL_V2_DIR),
        "tables_dir": str(tables_dir),
        "generic": generic_report,
        "paper": paper_report,
    }
    report_path = tables_dir / "final_v2_tables_export_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
