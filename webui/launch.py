"""Launcher for the MoniBox Streamlit WebUI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Start the Streamlit WebUI."""
    here = Path(__file__).resolve().parent
    app_path = here / "bootstrap.py"

    if not app_path.exists():
        print(f"Error: missing WebUI entry file: {app_path}")
        raise SystemExit(1)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    cmd.extend(sys.argv[1:])

    print("Starting MoniBox WebUI...")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopped.")
    except FileNotFoundError:
        print("Error: Streamlit is not installed. Run `uv sync --extra webui` first.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
