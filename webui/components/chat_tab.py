"""
webui/components/chat_tab.py

对话测试页 —— monibox-chat 的 GUI 版本。
支持文本/语音输入、TTS 播放、RAG 详情展开、性能指标。
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
from pathlib import Path

# 项目根目录注入（供 Streamlit 直接运行）
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.config import resolve_project_path
from app.settings import load_settings
from webui.adapters.web_tts import WebTTS

logger = logging.getLogger(__name__)


def _load_asr():
    """懒加载 ASR 模型。"""
    if "asr" in st.session_state:
        return st.session_state.asr

    try:
        from speech.whisper import FasterWhisperASR, WhisperASRConfig
    except ImportError:
        st.warning("faster-whisper 未安装，语音输入功能不可用。请运行 `uv sync --extra voice`")
        return None

    cfg = load_settings().speech.asr
    model_dir = resolve_project_path(cfg.model_path)
    if not Path(model_dir).exists():
        st.warning(f"ASR 模型目录不存在: {model_dir}")
        return None

    with st.spinner("正在加载 Whisper ASR 模型..."):
        asr = FasterWhisperASR(
            WhisperASRConfig(
                model_dir=model_dir,
                device=cfg.device,
                compute_type=cfg.compute_type,
                language=cfg.language,
            )
        )
    st.session_state.asr = asr
    return asr


def _get_or_create_session():
    """获取或创建 MoniSession（懒加载）。"""
    if "session" in st.session_state and st.session_state.get("session_profile") == st.session_state.get("current_profile"):
        return st.session_state.session

    from runtime.orchestrator import MoniSession, SessionConfig

    profile = st.session_state.get("current_profile", "")
    rt_cfg = load_settings(profile=profile if profile else None)

    llm_path = os.getenv("LLM_GGUF_PATH", "")
    if not llm_path:
        st.error("请在 .env 中设置 LLM_GGUF_PATH")
        return None

    rag_db = resolve_project_path(rt_cfg.rag.db_path)
    sess_cfg = SessionConfig(
        llm_path=llm_path,
        llm_ctx=rt_cfg.llm.ctx,
        llm_threads=rt_cfg.llm.threads,
        llm_gpu_layers=rt_cfg.llm.gpu_layers,
        tts_enabled=False,  # WebUI 自己控制 TTS
    )

    with st.spinner("正在加载 MoniSession（LLM + RAG）..."):
        session = MoniSession(rag_db, sess_cfg)

    st.session_state.session = session
    st.session_state.session_profile = profile
    return session


def _transcribe_audio(audio_bytes) -> str:
    """将音频字节转录为文字。"""
    asr = _load_asr()
    if asr is None:
        return ""

    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        Path(tmp_path).write_bytes(audio_bytes)
        with st.spinner("正在识别语音..."):
            text = asr.transcribe(tmp_path)
        return text
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _render_message(msg: dict):
    """渲染单条消息。"""
    role = msg["role"]
    content = msg["content"]

    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
    else:
        with st.chat_message("assistant"):
            st.markdown(f"**摩尼:** {content}")

            # 展开式详情
            if msg.get("trace"):
                with st.expander("查看处理详情", expanded=False):
                    trace = msg["trace"]

                    if trace.get("elapsed"):
                        st.markdown(f"**总耗时:** {trace['elapsed']:.2f}s")

                    if trace.get("rag_results"):
                        st.markdown("**RAG 检索结果**")
                        for i, r in enumerate(trace["rag_results"][:5], 1):
                            if r.distance <= 0.35:
                                level = "🟢 高置信"
                            elif r.distance <= 0.65:
                                level = "🟡 中等"
                            else:
                                level = "🔴 低证据"
                            st.markdown(
                                f"{i}. `{r.display_id}` {level} "
                                f"dist={r.distance:.4f} final={r.final_distance:.4f}"
                            )
                            st.caption(r.text[:200] + "..." if len(r.text) > 200 else r.text)

                    if trace.get("protocol_hit"):
                        st.markdown("**协议命中**")
                        st.json(trace["protocol_hit"])

            # TTS 播放
            if msg.get("tts_path") and Path(msg["tts_path"]).exists():
                st.audio(str(msg["tts_path"]), format="audio/wav")


def render_chat_tab():
    """渲染对话测试 Tab。"""
    st.header("💬 对话测试")
    st.caption("完整 RAG + LLM 对话链路，支持语音输入和 TTS 播放")

    # 初始化聊天记录
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 加载会话
    session = _get_or_create_session()
    if session is None:
        st.warning("MoniSession 加载失败，请检查配置。")
        return

    # 显示历史消息
    for msg in st.session_state.chat_history:
        _render_message(msg)

    # 语音输入
    audio_input = st.audio_input("🎤 按住说话（可选）")
    if audio_input is not None:
        text = _transcribe_audio(audio_input.read())
        if text:
            st.session_state.pending_input = text
            st.rerun()

    # 文本输入
    user_input = st.chat_input("输入消息...")

    # 如果有 pending_input（来自语音），使用它
    if "pending_input" in st.session_state:
        user_input = st.session_state.pop("pending_input")

    if user_input:
        # 添加用户消息
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
        })

        # 处理回复
        start = time.perf_counter()
        with st.spinner("思考中..."):
            reply = session.handle(user_input)
        elapsed = time.perf_counter() - start

        # 收集 trace 信息
        trace = {"elapsed": elapsed}

        # RAG 检索结果（额外调用一次用于展示）
        try:
            rr = session.rag.router.route(user_input, top_tags=2)
            dim = None if rr.cross_dimension else rr.dimension
            rag_results = session.rag.search(
                user_input, topk=5, pool_mult=4, dimension=dim, tags=rr.tags, max_per_group=1
            )
            trace["rag_results"] = rag_results
            trace["route"] = {"dimension": rr.dimension, "tags": rr.tags}
        except Exception as e:
            logger.warning("获取 RAG trace 失败: %s", e)

        # 协议命中
        try:
            prot_hit = session.prot.match(user_input, trace.get("route", {}).get("tags", []), [])
            if prot_hit:
                trace["protocol_hit"] = prot_hit
        except Exception as e:
            logger.warning("获取协议 trace 失败: %s", e)

        # TTS
        tts_path = None
        if st.session_state.get("tts_enabled", True):
            web_tts = st.session_state.get("web_tts")
            if web_tts is None:
                web_tts = WebTTS()
                st.session_state.web_tts = web_tts
            if web_tts.available:
                cfg = load_settings().speech.tts
                tts_path = web_tts.synthesize(reply, speed=cfg.sherpa_speed, sid=cfg.sherpa_sid)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": reply,
            "trace": trace,
            "tts_path": str(tts_path) if tts_path else None,
        })

        st.rerun()
