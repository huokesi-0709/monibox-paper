"""
webui/components/rag_tab.py

RAG 检索调试页 —— monibox-rag 的 GUI 版本。
支持查询输入、参数调节、结果表格展示、置信度可视化。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 项目根目录注入（供 Streamlit 直接运行）
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from app.config import resolve_project_path
from app.settings import load_settings

logger = logging.getLogger(__name__)


def _get_or_create_rag():
    """获取或创建 RagEngine（懒加载）。"""
    if "rag_engine" in st.session_state and st.session_state.get("rag_profile") == st.session_state.get("current_profile"):
        return st.session_state.rag_engine

    from runtime.rag_engine import RagEngine

    profile = st.session_state.get("current_profile", "")
    rt_cfg = load_settings(profile=profile if profile else None)
    rag_db = resolve_project_path(rt_cfg.rag.db_path)

    with st.spinner("正在加载 RagEngine..."):
        rag = RagEngine(rag_db)

    st.session_state.rag_engine = rag
    st.session_state.rag_profile = profile
    return rag


def render_rag_tab():
    """渲染 RAG 检索调试 Tab。"""
    st.header("🔍 RAG 检索调试")
    st.caption("快速验证知识库检索质量，查看距离分数和置信度")

    rag = _get_or_create_rag()
    if rag is None:
        st.error("RagEngine 加载失败")
        return

    # 输入区
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input("查询文本", placeholder="例如：我好冷", key="rag_query")
    with col2:
        topk = st.number_input("topk", min_value=1, max_value=20, value=5, key="rag_topk")
    with col3:
        auto_top_tags = st.number_input(
            "auto_top_tags", min_value=0, max_value=5, value=2, key="rag_tags"
        )

    if not query:
        st.info("输入查询文本后按回车开始检索")
        return

    # 执行检索
    with st.spinner("检索中..."):
        try:
            results = rag.auto_search(query, topk=int(topk), auto_top_tags=int(auto_top_tags))
        except Exception as e:
            st.error(f"检索失败: {e}")
            return

    # 路由信息
    try:
        rr = rag.router.route(query, top_tags=int(auto_top_tags))
        st.markdown(f"**路由结果:** dimension=`{rr.dimension}` tags=`{rr.tags}`")
    except Exception:
        pass

    if not results:
        st.warning("未检索到任何结果")
        return

    # 构建 DataFrame
    rag_max = float(st.session_state.get("rag_max_distance", 0.65))
    rows = []
    for i, r in enumerate(results, 1):
        if r.distance <= 0.35:
            level = "🟢 高置信"
        elif r.distance <= rag_max:
            level = "🟡 中等"
        else:
            level = "🔴 低证据"

        rows.append({
            "排名": i,
            "置信度": level,
            "ID": r.display_id,
            "维度": r.dimension,
            "风险": r.risk,
            "distance": round(r.distance, 4),
            "final_distance": round(r.final_distance, 4),
            "quality_score": r.quality_score,
            "status": r.status,
            "文本": r.text,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 详细文本展开
    st.markdown("**文本详情**")
    for row in rows:
        with st.expander(f"[{row['排名']}] {row['ID']} — {row['置信度']}"):
            st.markdown(f"**维度/风险:** {row['维度']} / {row['风险']}")
            st.markdown(f"**distance:** {row['distance']} | **final:** {row['final_distance']}")
            st.markdown(f"**文本:**")
            st.write(row["文本"])
