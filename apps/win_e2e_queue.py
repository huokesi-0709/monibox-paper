"""
apps/win_e2e_queue.py

基于最新 Phase 3 基于 Queue 的本地事件循环架构编写的测试脚本。
加载 ResourceManager 单例。
包含完整的 ASR (队列输入) -> Session 处理 -> TTS 生成 (推入队列) -> 音频线程播放 (流式输出) 的流程。
"""

import argparse
import os
import time

from monibox.config import settings
from monibox.core_loop.base import (
    EngineEvent,
    EventType,
    input_queue,
    output_queue,
)
from monibox.core_loop.resource_manager import global_resources
from monibox.hw.audio_player import AudioPlayerThread
from monibox.runtime.session import MoniSession, SessionConfig


def worker_session():
    """
    独立的大模型决策线程：
    不断从 input_queue 提取事件（TEXT/AUDIO等），调用 session 处理。
    如果有回复，session.handle_stream 或者底层 TTS引擎(Sherpa) 会自己把 PCM 推给 output_queue。
    """

    sess_cfg = SessionConfig(
        llm_path=os.getenv("LLM_GGUF_PATH", ""),
        llm_ctx=int(os.getenv("LLM_CTX", "2048")),
        llm_threads=int(os.getenv("LLM_THREADS", "6")),
        llm_gpu_layers=int(os.getenv("LLM_GPU_LAYERS", "0")),
        tts_enabled=True,
    )
    # 这时底层的 LLM/TTS 等都已经在 global_resources 中初始化好了
    session = MoniSession(
        settings.rag_db_path,
        sess_cfg,
        rag=global_resources.get_rag(),
        llm=global_resources.get_llm(),
        tts=global_resources.get_tts(),
    )

    print("[SessionWorker] 决策线程已启动")

    while True:
        event = input_queue.get()
        if event.event_type == EventType.SYS_CTRL and event.data == "exit":
            print("[SessionWorker] 收到退出指令")
            output_queue.put(event)  # 转发给播放线程
            break

        if event.event_type == EventType.TEXT_IN:
            text = event.data
            metadata = event.metadata
            print(f"[SessionWorker] 正在处理输入文本: {text}")

            # TODO: 后续可以改为流式处理 handle_stream
            reply = session.handle(
                text, events=metadata.get("events", []), auto_top_tags=2
            )
            print(f"[SessionWorker] 处理归档, 最终回复: {reply}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["text", "mic", "mic_vad"], default="text")
    ap.add_argument(
        "--text", default="你好，摩尼", help="text 模式下用来测试的初始语句"
    )
    args = ap.parse_args()

    # 1. 初始化全局大单例
    print("=" * 60)
    print("  MoniBox-KB Event Engine Test (Queue-based)")
    print("=" * 60)

    global_resources.initialize_all(
        rag_db_path=settings.rag_db_path,
        enable_asr=(args.mode != "text"),
        enable_tts=True,
    )

    # 修改全局 TTS 引擎使其为 queue 模式
    tts_engine = global_resources.get_tts()
    if tts_engine:
        tts_engine._playback_mode = "queue"
        print("[Engine] SherpaTTS 已切换为 Queue 输出模式")

    # 2. 启动音频播放独立线程
    player_thread = AudioPlayerThread()
    player_thread.start()

    # 3. 启动 Session 模拟独立线程（真实运行时，它是一个从外接传感器拿信息的永久循环）
    import threading

    session_thread = threading.Thread(target=worker_session, daemon=True)
    session_thread.start()

    time.sleep(1)  # 等待各线程 ready

    if args.mode == "text":
        while True:
            try:
                user_input = input("\n请输文本(输入 'q' 退出): ").strip()
                if user_input.lower() in ("q", "quit", "exit"):
                    input_queue.put(EngineEvent(EventType.SYS_CTRL, "exit"))
                    break
                if user_input:
                    # 抛入事件总线
                    input_queue.put(EngineEvent(EventType.TEXT_IN, user_input))
            except (KeyboardInterrupt, EOFError):
                input_queue.put(EngineEvent(EventType.SYS_CTRL, "exit"))
                break
    else:
        print("[MAIN] ASR 测试未完全合并，请先使用 text 体验单例和队列播放模式")
        input_queue.put(EngineEvent(EventType.SYS_CTRL, "exit"))

    session_thread.join()
    player_thread.join()
    print("主程序安全退出。")


if __name__ == "__main__":
    main()
