from __future__ import annotations

from app.config import PROJECT_ROOT
from knowledgekit import embedder


def test_embedding_model_uses_profile_path_by_default(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("RUNTIME_PROFILE", "paper_eval")

    configured = embedder._configured_embedding_model()
    resolved = embedder._resolve_model_ref(configured)

    assert configured == "models/embedding/bge-small-zh-v1.5"
    assert resolved == str((PROJECT_ROOT / configured).resolve())


def test_embedding_model_env_override_is_explicit(monkeypatch):
    monkeypatch.setenv("RUNTIME_PROFILE", "paper_eval")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom/local-model")

    assert embedder._configured_embedding_model() == "custom/local-model"


def test_embedding_fallback_warning_is_emitted_once(capsys):
    embedder.reset_embedding_model_cache()
    embedder._fallback_reason = "cached test failure"

    first = embedder.embed_texts(["地震被困"])
    second = embedder.embed_texts(["腿在流血"])
    captured = capsys.readouterr().out

    assert len(first[0]) == embedder.EMBED_DIM
    assert len(second[0]) == embedder.EMBED_DIM
    assert captured.count("model unavailable, fallback enabled") == 1
    assert captured.count("using hash fallback embeddings") == 1

    embedder.reset_embedding_model_cache()
