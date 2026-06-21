from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_GITIGNORE_PATTERNS = [
    ".env",
    ".env.*",
    "!.env.example",
    "build/rag.db",
    "build/runtime_pack.json",
]

ENV_EXAMPLE_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"hf_[A-Za-z0-9_]{20,}"),
]


def _gitignore_lines() -> list[str]:
    gitignore = ROOT / ".gitignore"
    assert gitignore.exists(), "Stage 0 repo hygiene broken: .gitignore is missing."
    return [
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_gitignore_keeps_stage0_private_and_build_artifact_rules() -> None:
    patterns = _gitignore_lines()
    missing = [
        pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in patterns
    ]

    assert not missing, (
        "Stage 0 repo hygiene broken: .gitignore is missing required pattern(s): "
        + ", ".join(missing)
    )


def test_gitignore_keeps_env_example_exception_after_env_wildcard() -> None:
    patterns = _gitignore_lines()
    env_wildcard_index = patterns.index(".env.*")
    env_example_exception_index = patterns.index("!.env.example")

    assert env_example_exception_index > env_wildcard_index, (
        "Stage 0 repo hygiene broken: !.env.example must appear after .env.* "
        "so the template remains commit-eligible."
    )


def test_env_example_exists_and_contains_no_obvious_real_secret() -> None:
    env_example = ROOT / ".env.example"
    assert env_example.exists(), (
        "Stage 0 repo hygiene broken: .env.example must exist as a safe template."
    )

    text = env_example.read_text(encoding="utf-8")
    matches = [
        pattern.pattern
        for pattern in ENV_EXAMPLE_SECRET_PATTERNS
        if pattern.search(text)
    ]

    assert not matches, (
        ".env.example appears to contain an obvious real secret pattern: "
        + ", ".join(matches)
    )
