"""Protocol test endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app.config import KNOWLEDGE_SRC

router = APIRouter(prefix="/api/protocol", tags=["protocol"])


@router.get("/catalog")
def catalog() -> dict[str, object]:
    protocols_path = KNOWLEDGE_SRC / "protocols.json"
    payload = json.loads(protocols_path.read_text(encoding="utf-8"))
    items = payload.get("protocols", [])

    return {
        "items": [
            {
                "protocol_id": item.get("protocol_id"),
                "name": item.get("name"),
                "priority": item.get("priority", 0),
                "trigger": item.get("trigger", {}),
                "action_count": len(item.get("actions", [])),
                "followup_count": len(item.get("followup_actions", [])),
            }
            for item in items
            if isinstance(item, dict)
        ],
        "count": len(items),
        "message": "ok",
    }
