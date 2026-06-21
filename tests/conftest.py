from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = ROOT / "build" / "pytest-work"


def pytest_configure() -> None:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TMP", str(TEST_TMP_ROOT))
    os.environ.setdefault("TEMP", str(TEST_TMP_ROOT))
    os.environ.setdefault("TMPDIR", str(TEST_TMP_ROOT))
    tempfile.tempdir = str(TEST_TMP_ROOT)


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    safe_name = "".join(
        ch if ch.isalnum() or ch in {"_", "-"} else "_"
        for ch in request.node.name[:80]
    )
    path = TEST_TMP_ROOT / f"{safe_name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path
