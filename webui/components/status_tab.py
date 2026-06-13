"""
webui/components/status_tab.py

系统状态页 —— 查看运行时配置、模型信息、Trace 日志。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 项目根目录注入（供 Streamlit 直接运行）
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from app.config import PROJECT_ROOT, resolve_project_path
from app.settings import load_settings


def render_status_tab():
    """渲染系统状态 Tab。"""
    st.header("📊 系统状态")
    st.caption("查看运行时配置、模型信息和最近的操作日志")

    profile = st.session_state.get("current_profile", "")
    rt_cfg = load_settings(profile=profile if profile else None)

    # 当前配置
    st.subheader("当前配置")
    try:
        cfg_dict = rt_cfg.model_dump()
        st.json(cfg_dict, expanded=False)
    except Exception as e:
        st.error(f"配置序列化失败: {e}")

    # 模型信息
    st.subheader("模型信息")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("LLM 上下文长度", rt_cfg.llm.ctx)
        st.metric("LLM 线程数", rt_cfg.llm.threads)
        st.metric("LLM GPU Layers", rt_cfg.llm.gpu_layers)
    with col2:
        st.metric("RAG top_k", rt_cfg.rag.top_k)
        st.metric("RAG max_distance", rt_cfg.rag.max_distance)
    with col3:
        st.metric("TTS 后端", rt_cfg.speech.tts.backend)
        st.metric("TTS max_chars", rt_cfg.speech.tts.max_chars)

    # 路径信息
    st.subheader("关键路径")
    st.markdown(f"- **RAG DB:** `{resolve_project_path(rt_cfg.rag.db_path)}`")
    st.markdown(f"- **ASR 模型:** `{resolve_project_path(rt_cfg.speech.asr.model_path)}`")
    st.markdown(f"- **TTS 模型:** `{resolve_project_path(rt_cfg.speech.tts.model_dir)}`")
    st.markdown(f"- **项目根目录:** `{PROJECT_ROOT}`")

    # Trace 日志
    st.subheader("Trace 日志（最近 50 条）")
    trace_path = PROJECT_ROOT / "build" / "runtime_logs" / "interaction_trace.jsonl"
    if trace_path.exists():
        lines = []
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            for line in all_lines[-50:]:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            st.error(f"读取日志失败: {e}")

        if lines:
            df = pd.json_normalize(lines)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("日志文件为空")
    else:
        st.info(f"日志文件不存在: {trace_path}")

    # 性能统计（如果 session 已加载）
    if "session" in st.session_state:
        session = st.session_state.session
        st.subheader("当前会话性能")
        try:
            if hasattr(session, "perf") and session.perf:
                st.markdown(f"**内存告警阈值:** {session.perf.warning_mb} MB")
        except Exception:
            pass
