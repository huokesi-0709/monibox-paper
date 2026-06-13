"""Session-backed chat service for the FastAPI layer."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import load_project_env, settings
from runtime.orchestrator import MoniSession, SessionConfig


class ChatServiceError(RuntimeError):
    """Raised when the chat service cannot fulfill a request."""


@dataclass
class ChatTurnResult:
    reply: str
    session_id: str
    messages: list[dict[str, str]]
    debug: dict[str, object]


@dataclass
class ManagedSession:
    session_id: str
    engine: MoniSession
    lock: threading.Lock = field(default_factory=threading.Lock)
    messages: list[dict[str, str]] = field(default_factory=list)


_sessions: dict[str, ManagedSession] = {}
_sessions_lock = threading.Lock()


def _build_session(session_id: str) -> ManagedSession:
    load_project_env()

    rag_db_path = Path(settings.rag_db_path)
    if not rag_db_path.exists():
        raise ChatServiceError(
            f"未找到 RAG 数据库：{rag_db_path}。请先确认知识库已经构建完成。"
        )

    sess_cfg = SessionConfig(
        llm_path=os.getenv("LLM_GGUF_PATH", ""),
        llm_ctx=int(os.getenv("LLM_CTX", "2048")),
        llm_threads=int(os.getenv("LLM_THREADS", "6")),
        llm_gpu_layers=int(os.getenv("LLM_GPU_LAYERS", "0")),
        tts_enabled=False,
    )
    engine = MoniSession(str(rag_db_path), sess_cfg)
    return ManagedSession(session_id=session_id, engine=engine)


def _get_or_create_session(session_id: str) -> ManagedSession:
    normalized = (session_id or "default").strip() or "default"

    with _sessions_lock:
        managed = _sessions.get(normalized)
        if managed is None:
            managed = _build_session(normalized)
            _sessions[normalized] = managed
        return managed


def _build_fallback_reply(engine: MoniSession) -> str:
    backend_name = getattr(engine.llm, "backend_name", "unknown")
    if backend_name == "null":
        return (
            "当前 API 已经接入真实会话链路，但还没有可用的 LLM 配置。"
            "请设置 `DEEPSEEK_API_KEY` 或 `LLM_GGUF_PATH` 后再试。"
        )
    return "本轮没有生成可用回复，请检查模型配置或运行时日志。"


def send_message(session_id: str, user_text: str) -> ChatTurnResult:
    message = (user_text or "").strip()
    if not message:
        raise ChatServiceError("消息不能为空。")

    managed = _get_or_create_session(session_id)

    with managed.lock:
        managed.messages.append({"role": "user", "content": message})
        reply = managed.engine.handle(message)
        if not reply:
            reply = _build_fallback_reply(managed.engine)
        managed.messages.append({"role": "assistant", "content": reply})

        debug: dict[str, Any] = {
            "backend": getattr(managed.engine.llm, "backend_name", "unknown"),
            "trace": managed.engine.last_trace,
            "message_count": len(managed.messages),
        }

        return ChatTurnResult(
            reply=reply,
            session_id=managed.session_id,
            messages=list(managed.messages),
            debug=debug,
        )
