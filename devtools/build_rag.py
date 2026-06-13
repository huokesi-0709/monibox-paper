"""Build the local RAG database from generated knowledge chunks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.config import GENERATED_DIR, PROJECT_ROOT, settings
from knowledgekit.embedder import embed_texts
from knowledgekit.fingerprint import sha256_fp
from knowledgekit.schema import normalize_chunk_fields, validate_normalized_chunk
from knowledgekit.store import RagDB
from knowledgekit.tags import TagRegistry
from knowledgekit.taxonomy import enrich_chunk_category, enrich_chunk_subcategory

DEFAULT_SOURCE = GENERATED_DIR / "12_chunks_rewritten.json"
DEFAULT_RUNTIME_PACK = PROJECT_ROOT / "build" / "runtime_pack.json"
EMBED_BATCH_SIZE = 64


def load_chunks(source_path: Path) -> list[dict]:
    data = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"输入文件不是数组: {source_path}")
    return [item for item in data if isinstance(item, dict)]


def normalize_chunks(chunks: list[dict]) -> list[dict]:
    registry = TagRegistry.load()
    normalized: list[dict] = []
    error_count = 0

    for index, raw in enumerate(chunks, start=1):
        chunk = dict(raw)
        normalize_chunk_fields(chunk)
        enrich_chunk_category(chunk)
        enrich_chunk_subcategory(chunk)

        chunk["tags"] = registry.canonicalize_list(chunk.get("tags", []))
        if not chunk.get("fingerprint"):
            chunk["fingerprint"] = sha256_fp(chunk["text"])

        errors = validate_normalized_chunk(chunk)
        if errors:
            error_count += 1
            raise ValueError(f"第 {index} 条 chunk 校验失败: {errors}")

        normalized.append(chunk)

    if error_count:
        raise ValueError(f"存在 {error_count} 条无效 chunk")
    return normalized


def embed_chunks(chunks: list[dict]) -> list[list[float]]:
    vectors: list[list[float]] = []
    texts = [str(chunk["text"]) for chunk in chunks]
    total = len(texts)

    for start in range(0, total, EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        vectors.extend(embed_texts(batch))
        print(f"[build_rag] embedded {min(start + len(batch), total)}/{total}")

    if len(vectors) != total:
        raise RuntimeError("向量数量与 chunk 数量不一致")
    return vectors


def write_runtime_pack(
    chunks: list[dict], runtime_pack_path: Path, source_path: Path
) -> None:
    category_counts = Counter(str(chunk.get("category") or "") for chunk in chunks)
    sub_category_counts = Counter(
        str(chunk.get("sub_category") or "") for chunk in chunks
    )
    tag_counts = Counter(
        tag for chunk in chunks for tag in chunk.get("tags", []) if str(tag).strip()
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema_version": "stage_3c_v1",
        "chunk_count": len(chunks),
        "source": str(source_path.relative_to(PROJECT_ROOT)),
        "rag_db_path": settings.rag_db_path,
        "top_categories": category_counts.most_common(20),
        "top_sub_categories": sub_category_counts.most_common(20),
        "top_tags": tag_counts.most_common(50),
    }

    runtime_pack_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_pack_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build(source_path: Path, db_path: Path, runtime_pack_path: Path) -> None:
    print(f"[build_rag] source: {source_path}")
    chunks = load_chunks(source_path)
    print(f"[build_rag] loaded chunks: {len(chunks)}")

    normalized = normalize_chunks(chunks)
    vectors = embed_chunks(normalized)

    rag_db = RagDB(str(db_path))
    rag_db.create_tables()
    rag_db.insert_chunks(normalized, vectors)

    write_runtime_pack(normalized, runtime_pack_path, source_path)

    print(f"[build_rag] wrote db: {db_path}")
    print(f"[build_rag] wrote runtime pack: {runtime_pack_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MoniBox rag.db locally.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Path to the generated chunk JSON file.",
    )
    parser.add_argument(
        "--db-path",
        default=settings.rag_db_path,
        help="Target SQLite vector database path.",
    )
    parser.add_argument(
        "--runtime-pack-path",
        default=settings.runtime_pack_path,
        help="Target runtime pack JSON path.",
    )
    args = parser.parse_args()

    build(
        source_path=Path(args.source),
        db_path=Path(args.db_path),
        runtime_pack_path=Path(args.runtime_pack_path),
    )


if __name__ == "__main__":
    main()
