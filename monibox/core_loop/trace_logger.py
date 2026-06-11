"""
Structured runtime trace logging for Stage E observability.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_LOGGER_LOCK = threading.Lock()
_LOGGER_SINGLETON: RuntimeTraceLogger | None = None
_ID_LOCK = threading.Lock()
_ID_SEQ = 0


def new_interaction_id(prefix: str = "turn") -> str:
    global _ID_SEQ
    with _ID_LOCK:
        _ID_SEQ += 1
        seq = _ID_SEQ
    stamp = int(time.time() * 1000)
    return f"{prefix}-{stamp}-{seq:04d}"


class RuntimeTraceLogger:
    def __init__(self, path: str | Path, enabled: bool = True):
        self.enabled = bool(enabled)
        self.path = Path(path)
        self._lock = threading.Lock()

    def log(
        self, kind: str, *, interaction_id: str | None = None, **fields: Any
    ) -> None:
        if not self.enabled:
            return

        record = {"ts": datetime.now().isoformat(timespec="milliseconds"), "kind": kind}
        if interaction_id:
            record["interaction_id"] = interaction_id
        for key, value in fields.items():
            if value is not None:
                record[key] = value

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def get_runtime_trace_logger() -> RuntimeTraceLogger:
    global _LOGGER_SINGLETON
    with _LOGGER_LOCK:
        if _LOGGER_SINGLETON is None:
            enabled = os.getenv("RUNTIME_TRACE_ENABLED", "1") == "1"
            raw_path = os.getenv(
                "RUNTIME_TRACE_PATH", "build/runtime_logs/interaction_trace.jsonl"
            )
            path = Path(raw_path)
            if not path.is_absolute():
                path = Path(os.getcwd()) / path
            _LOGGER_SINGLETON = RuntimeTraceLogger(path=path, enabled=enabled)
        return _LOGGER_SINGLETON
