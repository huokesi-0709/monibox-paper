"""
webui/components/protocol_tab.py

协议测试页 —— monibox-protocol-mock 的 GUI 版本。
支持查询输入、模拟事件、协议命中/兜底结果展示、护栏日志。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 项目根目录注入（供 Streamlit 直接运行）
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.config import resolve_project_path
from app.settings import load_settings
from runtime.guard import SafetyGuard
from runtime.primitives import MockHardware
from runtime.protocol_matcher import ProtocolEngine
from runtime.rag_engine import RagEngine

logger = logging.getLogger(__name__)


def _get_or_create_protocol_testers():
    """获取或创建协议测试所需的引擎（懒加载）。"""
    key = "protocol_testers"
    profile = st.session_state.get("current_profile", "")
    if key in st.session_state and st.session_state.get("protocol_profile") == profile:
        return st.session_state[key]

    rt_cfg = load_settings(profile=profile if profile else None)
    rag_db = resolve_project_path(rt_cfg.rag.db_path)

    with st.spinner("正在加载测试引擎..."):
        hw = MockHardware()
        rag = RagEngine(rag_db)
        prot = ProtocolEngine()
        guard = SafetyGuard()

    testers = {"hw": hw, "rag": rag, "prot": prot, "guard": guard}
    st.session_state[key] = testers
    st.session_state.protocol_profile = profile
    return testers


def render_protocol_tab():
    """渲染协议测试 Tab。"""
    st.header("📋 协议测试")
    st.caption("验证协议优先链路：协议命中 → 动作链执行 → 护栏检查")

    testers = _get_or_create_protocol_testers()
    if testers is None:
        st.error("测试引擎加载失败")
        return

    hw = testers["hw"]
    rag = testers["rag"]
    prot = testers["prot"]
    guard = testers["guard"]

    # 输入区
    query = st.text_input("查询文本", placeholder="例如：我腿在流血", key="prot_query")
    events_str = st.text_input(
        "模拟事件（逗号分隔）",
        placeholder="例如: imu_strong_shake,smoke_detected",
        key="prot_events",
    )

    if not query:
        st.info("输入查询文本后按回车开始测试")
        return

    events = [e.strip() for e in events_str.split(",") if e.strip()]

    # 1) 路由
    with st.spinner("测试中..."):
        rr = rag.router.route(query, top_tags=2)
        st.markdown(f"**路由结果:** dimension=`{rr.dimension}` tags=`{rr.tags}`")

        # 2) 协议匹配
        hit = prot.match(query, rr.tags, events)

    if hit:
        st.success(f"✅ 协议命中: `{hit['protocol_id']}` — {hit['name']}")

        st.markdown("**动作链**")
        for i, a in enumerate(hit.get("actions", []), 1):
            t = a.get("type")
            col1, col2 = st.columns([1, 4])
            with col1:
                st.code(t.upper() if t else "UNKNOWN")
            with col2:
                if t == "tts":
                    raw_text = a.get("text", "")
                    style = a.get("style", "default")
                    res = guard.check(raw_text)

                    if res.level == "allow":
                        st.markdown(f"🟢 **{res.safe_text}** (style={style})")
                    elif res.level == "rewrite":
                        st.markdown(f"🟡 **{res.safe_text}**")
                        st.caption(f"rewrite reasons: {res.reasons}")
                    else:
                        st.markdown(f"🔴 **{res.safe_text}**")
                        st.caption(f"block reasons: {res.reasons}")

                    # 模拟硬件调用
                    hw.tts(res.safe_text, style=style)

                elif t == "led":
                    pattern = a.get("pattern", {})
                    st.json(pattern)
                    hw.led(pattern)

                elif t == "screen":
                    text = a.get("text", "")
                    ms = int(a.get("ms", 2000))
                    st.markdown(f"显示 `{text}` ({ms}ms)")
                    hw.screen(text, ms=ms)
    else:
        st.info("❌ 未命中协议，fallback 到 RAG")

        # 3) RAG 兜底
        res_list = rag.auto_search(query, topk=5, auto_top_tags=2)

        if not res_list:
            st.warning("RAG 也未检索到结果")
            return

        st.markdown("**RAG 兜底结果**")
        for i, r in enumerate(res_list, 1):
            with st.expander(f"[{i}] {r.display_id} ({r.dimension}/{r.risk})"):
                st.markdown(f"dist={r.distance:.4f} final={r.final_distance:.4f}")

                # 每条走护栏
                res = guard.check(r.text)
                if res.level == "allow":
                    st.success(f"🟢 allow: {res.safe_text}")
                elif res.level == "rewrite":
                    st.warning(f"🟡 rewrite ({res.reasons}): {res.safe_text}")
                else:
                    st.error(f"🔴 block ({res.reasons}): {res.safe_text}")

                hw.tts(res.safe_text, style="calm_clear")
