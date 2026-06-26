from __future__ import annotations

import json

from experiments.export_selected_cases import export_selected_cases
from experiments.final_v2_utils import FINAL_V2_DIR


def main() -> int:
    report = export_selected_cases(FINAL_V2_DIR, FINAL_V2_DIR / "cases")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
