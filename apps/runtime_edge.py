"""
Backward-compatible entrypoint.
Prefer: uv run monibox --mode text
"""
from monibox.cli import main

if __name__ == "__main__":
    main()
