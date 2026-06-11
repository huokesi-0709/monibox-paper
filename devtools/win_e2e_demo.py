"""
Windows 端到端语音链路实验入口。

关键：每轮 session.handle() 返回后，sleep 一小段冷却时间，
避免立刻又进入 VAD 监听把 TTS 声音吃进去，也避免音频设备争用。
"""

import argparse
import os
import time

from app.config import settings
from runtime.orchestrator import MoniSession, SessionConfig
from speech.recorder import record
from speech.vad import VadConfig, record_vad
from speech.whisper import (
    FasterWhisperASR,
    WhisperASRConfig,
    build_default_initial_prompt,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["mic", "mic_vad", "text"], default="mic")
    ap.add_argument("--text", default="")
    ap.add_argument("--events", default="", help="逗号分隔，如 imu_strong_shake")
    ap.add_argument("--auto_top_tags", type=int, default=2)
    ap.add_argument("--no_tts", action="store_true", help="只在控制台输出，不播放语音")
    ap.add_argument("--once", action="store_true", help="mic_vad 模式只跑一轮就退出")
    args = ap.parse_args()

    events = [e.strip() for e in args.events.split(",") if e.strip()]

    llm_path = os.getenv("LLM_GGUF_PATH", "")
    if not llm_path:
        raise RuntimeError("请在 .env 中设置 LLM_GGUF_PATH")

    sess_cfg = SessionConfig(
        llm_path=llm_path,
        llm_ctx=int(os.getenv("LLM_CTX", "2048")),
        llm_threads=int(os.getenv("LLM_THREADS", "6")),
        llm_gpu_layers=int(os.getenv("LLM_GPU_LAYERS", "0")),
        tts_enabled=(not args.no_tts),
    )
    session = MoniSession(settings.rag_db_path, sess_cfg)

    # text 模式不需要 ASR
    if args.mode == "text":
        user_text = args.text.strip()
        if not user_text:
            raise RuntimeError("--mode text 时必须提供 --text")
        print("[TEXT INPUT]", user_text)
        session.handle(user_text, events=events, auto_top_tags=args.auto_top_tags)
        return

    # ASR 初始化（mic / mic_vad 才需要）
    asr_cfg = WhisperASRConfig(
        model_dir=os.getenv("WHISPER_MODEL_DIR", "models/asr/faster-whisper-small"),
        device=os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        language=os.getenv("WHISPER_LANGUAGE", "zh"),
        initial_prompt=os.getenv("WHISPER_INITIAL_PROMPT")
        or build_default_initial_prompt(),
    )
    asr = FasterWhisperASR(asr_cfg)

    # mic：按回车录固定秒数
    if args.mode == "mic":
        sec = float(os.getenv("REC_SECONDS", "4"))
        sr = int(os.getenv("REC_SAMPLE_RATE", "16000"))

        print(f"按回车开始录音 {sec}s ...")
        input()
        audio = record(seconds=sec, sample_rate=sr)
        print("识别中...")
        user_text = asr.transcribe(audio)
        print("[ASR]", user_text)

        if not user_text:
            print("未识别到内容")
            return

        session.handle(user_text, events=events, auto_top_tags=args.auto_top_tags)
        return

    # mic_vad：持续监听
    sr = int(os.getenv("REC_SAMPLE_RATE", "16000"))
    vad_cfg = VadConfig(
        sample_rate=sr,
        start_rms=float(os.getenv("VAD_START_RMS", "0.012")),
        end_silence_ms=int(os.getenv("VAD_END_SIL_MS", "800")),
        max_seconds=float(os.getenv("VAD_MAX_SEC", "12")),
        pre_roll_ms=int(os.getenv("VAD_PRE_ROLL_MS", "300")),
    )

    # 关键：TTS 播放后冷却，避免马上又监听到（包括避免录到自己的 TTS）
    cooldown_sec = float(os.getenv("MIC_COOLDOWN_SEC", "0.6"))

    print("mic_vad 模式：开始持续监听（检测到说话会自动识别）...")
    print(
        "提示：不触发/误触发可调 VAD_START_RMS；识别差可调 VAD_PRE_ROLL_MS（200~500）"
    )

    while True:
        audio = record_vad(vad_cfg)
        if audio is None:
            continue

        print("\n识别中...")
        user_text = asr.transcribe(audio)
        print("[ASR]", user_text)

        if user_text:
            session.handle(user_text, events=events, auto_top_tags=args.auto_top_tags)

        # 冷却：等 TTS 播完后再开始下一轮监听（避免设备争用/自激/你觉得“没播”）
        time.sleep(cooldown_sec)

        if args.once:
            break


if __name__ == "__main__":
    main()
