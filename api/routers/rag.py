"""RAG endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from runtime.rag_engine import RagEngine

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/search")
def search(query: str = "", top_k: int = 5) -> dict[str, object]:
    text = (query or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="查询内容不能为空。")

    rag_db_path = Path(settings.rag_db_path)
    if not rag_db_path.exists():
        raise HTTPException(status_code=400, detail=f"未找到 RAG 数据库：{rag_db_path}")

    engine = RagEngine(str(rag_db_path))
    routing = engine.router.route(text, top_tags=2)
    dimension = None if routing.cross_dimension else routing.dimension
    results = engine.search(
        text,
        topk=max(1, min(top_k, 20)),
        pool_mult=max(8, top_k * 2),
        dimension=dimension,
        tags=routing.tags,
        max_per_group=1,
    )

    return {
        "query": text,
        "top_k": top_k,
        "routing": {
            "dimension": routing.dimension,
            "cross_dimension": routing.cross_dimension,
            "tags": routing.tags,
        },
        "results": [
            {
                "chunk_id": item.chunk_id,
                "display_id": item.display_id,
                "group_id": item.group_id,
                "text": item.text,
                "category": item.category,
                "sub_category": item.sub_category,
                "dimension": item.dimension,
                "risk": item.risk,
                "scene": item.scene,
                "source_id": item.source_id,
                "status": item.status,
                "quality_score": item.quality_score,
                "priority": item.priority,
                "distance": item.distance,
                "final_distance": item.final_distance,
            }
            for item in results
        ],
        "message": "ok" if results else "当前没有命中结果。",
    }
