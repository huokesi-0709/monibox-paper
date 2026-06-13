"""
webui/app.py

MoniBox WebUI —— Streamlit 主入口。

启动方式:
    uv run --extra webui streamlit run webui/app.py

完整依赖（如需使用全部功能）:
    uv sync --extra webui --extra knowledge --extra voice --extra local-llm
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Streamlit 运行时的目录不在 sys.path 中，需手动注入项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from app.config import PROJECT_ROOT, load_project_env
from app.settings import load_settings

# 加载项目环境变量
load_project_env()

# ---------- Streamlit 页面配置 ----------
st.set_page_config(
    page_title="MoniBox WebUI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- 侧边栏 ----------
def render_sidebar():
    """渲染左侧边栏。"""
    with st.sidebar:
        st.title("🤖 MoniBox")
        st.caption("图形化测试前端")
        st.divider()

        # Profile 选择
        profiles_dir = PROJECT_ROOT / "profiles"
        profiles = [""]
        if profiles_dir.exists():
            profiles = sorted(
                [p.stem for p in profiles_dir.glob("*.yaml") if p.stem != "base"]
            )
            profiles.insert(0, "base")

        current = st.session_state.get("current_profile", "")
        try:
            idx = profiles.index(current) if current in profiles else 0
        except ValueError:
            idx = 0

        selected = st.selectbox(
            "选择 Profile",
            options=profiles,
            index=idx,
            format_func=lambda x: x if x else "默认 (base)",
            help="切换平台配置（如 windows / text_mvp / radxa 等）",
        )

        if selected != current:
            st.session_state.current_profile = selected
            # 清除已缓存的模型实例，让它们下次重新加载
            for key in ["session", "rag_engine", "protocol_testers", "asr", "web_tts"]:
                st.session_state.pop(key, None)
            st.rerun()

        # 模型状态
        st.divider()
        st.markdown("**模型状态**")

        session_loaded = "session" in st.session_state
        rag_loaded = "rag_engine" in st.session_state
        asr_loaded = "asr" in st.session_state
        tts_loaded = "web_tts" in st.session_state and st.session_state.web_tts.available

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"{'🟢' if session_loaded else '⚪'} LLM+对话")
            st.markdown(f"{'🟢' if rag_loaded else '⚪'} RAG")
        with col2:
            st.markdown(f"{'🟢' if asr_loaded else '⚪'} ASR")
            st.markdown(f"{'🟢' if tts_loaded else '⚪'} TTS")

        # 快捷操作
        st.divider()
        if st.button("🔄 重新加载模型", use_container_width=True):
            for key in ["session", "rag_engine", "protocol_testers", "asr", "web_tts"]:
                st.session_state.pop(key, None)
            st.rerun()

        if st.button("🗑️ 清空聊天记录", use_container_width=True):
            st.session_state.pop("chat_history", None)
            st.rerun()

        # TTS 开关
        st.divider()
        tts_enabled = st.toggle(
            "🔊 TTS 播放",
            value=st.session_state.get("tts_enabled", True),
            help="控制是否自动播放系统回复的语音",
        )
        st.session_state.tts_enabled = tts_enabled

        # 调试模式
        debug_mode = st.toggle(
            "🐛 调试信息",
            value=st.session_state.get("debug_mode", False),
            help="在对话页面显示详细的处理 trace",
        )
        st.session_state.debug_mode = debug_mode

        st.divider()
        st.caption(f"项目根目录: `{PROJECT_ROOT}`")


# ---------- 主区域 ----------
def render_main():
    """渲染主区域 Tab 内容。"""
    tab_chat, tab_rag, tab_protocol, tab_status = st.tabs([
        "💬 对话测试",
        "🔍 RAG 检索",
        "📋 协议测试",
        "📊 系统状态",
    ])

    with tab_chat:
        try:
            from webui.components.chat_tab import render_chat_tab
            render_chat_tab()
        except ImportError as e:
            st.error(f"对话模块加载失败: {e}")
            st.info("如需使用对话功能，请安装完整依赖: `uv sync --extra webui --extra knowledge --extra voice --extra local-llm`")

    with tab_rag:
        try:
            from webui.components.rag_tab import render_rag_tab
            render_rag_tab()
        except ImportError as e:
            st.error(f"RAG 模块加载失败: {e}")
            st.info("如需使用 RAG 功能，请安装知识库依赖: `uv sync --extra knowledge`")

    with tab_protocol:
        try:
            from webui.components.protocol_tab import render_protocol_tab
            render_protocol_tab()
        except ImportError as e:
            st.error(f"协议测试模块加载失败: {e}")
            st.info("如需使用协议测试功能，请安装完整依赖: `uv sync --extra knowledge`")

    with tab_status:
        from webui.components.status_tab import render_status_tab
        render_status_tab()


# ---------- 入口 ----------
def main():
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
