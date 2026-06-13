"""Status and health endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app.config import PROJECT_ROOT, load_project_env, settings as legacy_settings
from app.settings import get_settings

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/health")
def health() -> dict[str, object]:
    load_project_env()
    settings = get_settings()
    rag_db_path = Path(legacy_settings.rag_db_path)
    runtime_pack_path = Path(legacy_settings.runtime_pack_path)
    runtime_pack_summary: dict[str, object] = {}

    if runtime_pack_path.exists():
        try:
            runtime_pack_summary = json.loads(
                runtime_pack_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            runtime_pack_summary = {"error": "runtime_pack.json is invalid"}

    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "profile": settings.app.mode,
        "llm_backend": settings.llm.backend,
        "tts_backend": settings.speech.tts.backend,
        "rag_db_path": str(rag_db_path),
        "rag_db_exists": rag_db_path.exists(),
        "runtime_pack_path": str(runtime_pack_path),
        "runtime_pack_exists": runtime_pack_path.exists(),
        "runtime_pack_summary": runtime_pack_summary,
    }
