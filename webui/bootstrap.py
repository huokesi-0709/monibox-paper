"""Bootstrap the WebUI after fixing Python import paths."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_TARGET = _SCRIPT_DIR / "main.py"


def _clean_sys_path() -> None:
    cleaned_sys_path: list[str] = []
    for entry in sys.path:
        try:
            if Path(entry).resolve() == _SCRIPT_DIR:
                continue
        except OSError:
            pass
        cleaned_sys_path.append(entry)

    sys.path[:] = cleaned_sys_path
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))


def main() -> None:
    _clean_sys_path()
    runpy.run_path(str(_TARGET), run_name="__main__")


if __name__ == "__main__":
    main()
