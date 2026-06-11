"""
devtools/chat.py

纯文本交互式对话入口 —— 专注于 RAG 对话质量调试。
不依赖 ASR / TTS / 麦克风 / 音频设备。

用法：
    python -m devtools.chat                  # 完整模式（RAG + LLM）
    python -m devtools.chat --no_llm         # 仅查看 RAG 检索结果，不加载 LLM
    python -m devtools.chat --query "我好冷"  # 单条查询模式
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from app.config import settings

load_dotenv()


def run_rag_only(query: str, rag_db_path: str) -> None:
    """
    仅运行 RAG 检索，显示检索结果，不加载 LLM。
    用于快速验证知识库质量。
    """
    from runtime.rag_engine import RagEngine

    rag = RagEngine(rag_db_path)
    rr = rag.router.route(query, top_tags=2)

    print(f"\n路由结果: dimension={rr.dimension} tags={rr.tags}")

    dim = None if rr.cross_dimension else rr.dimension
    results = rag.search(
        query, topk=8, pool_mult=8, dimension=dim, tags=rr.tags, max_per_group=1
    )

    if not results:
        # 无标签限制再搜一次
        results = rag.search(
            query, topk=8, pool_mult=8, dimension=None, tags=None, max_per_group=1
        )

    rag_max = float(os.getenv("RAG_MAX_DISTANCE", "0.65"))
    print(f"RAG_MAX_DISTANCE={rag_max}")
    print(f"检索到 {len(results)} 条结果:\n")

    for i, r in enumerate(results):
        # NOTE: 标记证据强度
        if r.distance <= 0.35:
            level = "🟢 高置信"
        elif r.distance <= rag_max:
            level = "🟡 中等"
        else:
            level = "🔴 低证据"

        print(
            f"  [{i + 1}] {level} distance={r.distance:.4f} final={r.final_distance:.4f}"
        )
        print(f"      ID: {r.display_id}")
        print(f"      文本: {r.text}")
        print()


def run_full(rag_db_path: str, single_query: str = "") -> None:
    """完整模式：RAG + LLM 对话"""
    from runtime.orchestrator import MoniSession, SessionConfig

    llm_path = os.getenv("LLM_GGUF_PATH", "")
    if not llm_path:
        print("错误：请在 .env 中设置 LLM_GGUF_PATH")
        sys.exit(1)

    print(f"  LLM: {llm_path}")
    print("正在加载模型，请稍候...")

    sess_cfg = SessionConfig(
        llm_path=llm_path,
        llm_ctx=int(os.getenv("LLM_CTX", "2048")),
        llm_threads=int(os.getenv("LLM_THREADS", "6")),
        llm_gpu_layers=int(os.getenv("LLM_GPU_LAYERS", "0")),
        tts_enabled=True,
    )
    session = MoniSession(rag_db_path, sess_cfg)
    print("模型加载完成！\n")

    if single_query:
        reply = session.handle(single_query)
        print(f"摩尼: {reply}")
        return

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("q", "quit", "exit"):
            print("再见。")
            break

        reply = session.handle(user_input)
        print(f"摩尼: {reply}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="MoniBox-KB 文本对话")
    ap.add_argument(
        "--no_llm", action="store_true", help="仅查看 RAG 检索结果，不加载 LLM"
    )
    ap.add_argument("--query", default="", help="单条查询（不进入交互循环）")
    args = ap.parse_args()

    print("=" * 50)
    print("  MoniBox-KB 文本对话模式")
    mode_label = "RAG 检索" if args.no_llm else "RAG + LLM"
    print(f"  模式: {mode_label}")
    print(f"  RAG DB: {settings.rag_db_path}")
    print("=" * 50)

    if args.no_llm:
        # NOTE: 仅 RAG 模式：快速验证检索质量，不需要 LLM 模型
        if args.query:
            run_rag_only(args.query, settings.rag_db_path)
        else:
            print("输入查询文本，输入 q 退出\n")
            while True:
                try:
                    q = input("查询: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n再见。")
                    break
                if not q:
                    continue
                if q.lower() in ("q", "quit", "exit"):
                    print("再见。")
                    break
                run_rag_only(q, settings.rag_db_path)
    else:
        run_full(settings.rag_db_path, single_query=args.query)


if __name__ == "__main__":
    main()
