from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATHS = [
    ".env",
    ".uv-cache",
    "frontend/node_modules",
    "frontend/dist",
    "frontend/.npm-cache",
    "build/runtime_logs",
]

SKIP_DIRS = {
    ".git",
    ".venv",
    ".npm-cache",
    ".pytest_cache",
    ".uv-cache",
    "dist",
    "node_modules",
    "runtime_logs",
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(
        r"(?m)^\s*(?:[A-Z0-9_]*API_KEY|SECRET|TOKEN)\s*=\s*"
        r"(?!<[^>\r\n]+>|your_|$)[^\s#]+"
    ),
]


def _git_paths(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.splitlines()


def _is_forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized == ".env"
        or normalized.startswith(".env.")
        and normalized != ".env.example"
        or normalized.startswith(".uv-cache/")
        or "/__pycache__/" in normalized
        or normalized.endswith(".pyc")
        or normalized.startswith("frontend/node_modules/")
        or normalized.startswith("frontend/dist/")
        or normalized.startswith("frontend/.npm-cache/")
        or normalized.startswith("build/runtime_logs/")
    )


def test_private_files_are_not_commit_candidates() -> None:
    tracked = _git_paths("ls-files")
    unignored = _git_paths("ls-files", "--others", "--exclude-standard")
    forbidden = [path for path in tracked + unignored if _is_forbidden(path)]

    assert not forbidden, "private/cache files can be committed:\n" + "\n".join(
        forbidden
    )


def test_example_env_contains_only_placeholders() -> None:
    env_example = ROOT / ".env.example"
    assert env_example.exists(), ".env.example is required"

    text = env_example.read_text(encoding="utf-8")
    matches = [
        pattern.pattern for pattern in SECRET_PATTERNS for _ in pattern.finditer(text)
    ]
    assert not matches, ".env.example appears to contain a real secret"


def test_tracked_text_files_do_not_contain_obvious_secrets() -> None:
    offenders: list[str] = []
    for rel in _git_paths("ls-files"):
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            offenders.append(rel)

    assert not offenders, "tracked files may contain secrets:\n" + "\n".join(offenders)
