"""
knowledgekit/embedder.py

作用：
- 在构建期（PC）为文本生成 embedding 向量，用于写入 sqlite-vec（rag.db）
- 支持使用“本地模型目录”，避免重复下载



推荐做法：
- 在 .env 里配置 EMBEDDING_MODEL=models/embedding/bge-small-zh-v1.5
- 本文件会自动把相对路径拼成项目根目录下的绝对路径
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import numpy as np

from app.config import PROJECT_ROOT, settings

_model: Any | None = None

EMBED_DIM = 512


def _resolve_model_ref(model_id_or_path: str) -> str:
    """
    把 .env 中的 EMBEDDING_MODEL 解析为真正描述符：
    - 如果是相对路径：按 PROJECT_ROOT 拼成绝对路径
    - 如果是绝对路径：直接使用
    - 如果是 HuggingFace 模型名：原样返回（但你现在不需要）
    """
    s = (model_id_or_path or "").strip()
    if not s:
        raise ValueError("EMBEDDING_MODEL 为空，请在 .env 中设置")

    p = Path(s)

    # 明确的本地相对路径：相对于项目根目录
    is_local_hint = s.startswith((".", "models/", "models\\"))
    if not p.is_absolute() and is_local_hint:
        p = (PROJECT_ROOT / p).resolve()
        return str(p)

    # 绝对路径
    if p.is_absolute():
        return str(p)

    # 其余情况按模型 ID 处理，例如 BAAI/bge-small-zh-v1.5
    return s


def get_model():
    """
    单例加载 embedding 模型，避免重复加载占内存。
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "缺少 sentence-transformers，无法加载 embedding 模型。"
                "请先执行 `uv sync --extra knowledge`。"
            ) from exc

        model_ref = _resolve_model_ref(settings.embedding_model)

        # 仅在本地目录模式下强制离线，避免把 HuggingFace 模型 ID 误伤。
        if Path(model_ref).exists():
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        # 给出明确提示，方便你确认它在用本地路径
        print(f"[embedding] loading model from: {model_ref}")

        # 检查关键文件是否存在，避免 silent fail
        if Path(model_ref).exists():
            cfg = Path(model_ref) / "config_sentence_transformers.json"
            if not cfg.exists():
                print(
                    "[embedding][WARN] 未发现 config_sentence_transformers.json，"
                    "如果加载失败，请确认该目录是 sentence-transformers 格式模型。"
                )

        local_files_only = Path(model_ref).exists()
        load_attempts = [
            {
                "device": "cpu",
                "local_files_only": local_files_only,
                "model_kwargs": {"use_safetensors": False},
            },
            {"device": "cpu", "local_files_only": local_files_only},
        ]
        last_exc: Exception | None = None
        for kwargs in load_attempts:
            try:
                _model = SentenceTransformer(model_ref, **kwargs)
                break
            except TypeError as exc:
                last_exc = exc
                continue
            except OSError as exc:
                last_exc = exc
                continue

        if _model is None:
            raise RuntimeError(
                "embedding 模型加载失败。请确认本地模型完整，并检查 Windows 分页文件/可用内存。"
            ) from last_exc

    return _model


def _hash_token_index(token: str) -> tuple[int, float]:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "little") % EMBED_DIM
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return bucket, sign


def _fallback_embed_text(text: str) -> list[float]:
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return vec.tolist()

    tokens: list[str] = []
    tokens.extend(part for part in normalized.split(" ") if part)
    raw = normalized.replace(" ", "")
    tokens.extend(raw[i : i + 2] for i in range(max(0, len(raw) - 1)))

    for token in tokens:
        bucket, sign = _hash_token_index(token)
        vec[bucket] += sign

    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


def _fallback_embed_texts(texts: list[str]) -> list[list[float]]:
    print("[embedding][WARN] using hash fallback embeddings")
    return [_fallback_embed_text(text) for text in texts]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    批量生成向量（normalize_embeddings=True 输出单位向量，适合余弦相似度）
    """
    try:
        model = get_model()
    except Exception as exc:
        print(f"[embedding][WARN] model unavailable, fallback enabled: {exc}")
        return _fallback_embed_texts(texts)

    emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    emb = np.asarray(emb, dtype=np.float32)
    return emb.tolist()
