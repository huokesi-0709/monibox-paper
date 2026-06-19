"""
Edge runtime entrypoint for text and mic_vad modes.
"""

from __future__ import annotations

import argparse
import os
import time

from app.log import get_logger, setup_logging
from app.settings import get_settings
from core.engine import MainEngine
from core.shared import EngineEvent, EventType, input_queue

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
if not os.getenv("WHISPER_THREADS"):
    os.environ["OMP_NUM_THREADS"] = "2"

setup_logging()
logger = get_logger("RuntimeEdge")


_PROFILE_CHOICES = [
    "windows",
    "radxa",
    "radxa_extreme",
    "radxa_full",
    "radxa_light",
    "paper_eval",
    "paper_text",
    "text_mvp",
    "voice_mvp",
]


def _describe_input_device() -> str:
    configured = (
        os.getenv("REC_INPUT_DEVICE") or os.getenv("REC_DEVICE") or ""
    ).strip()
    try:
        import sounddevice as sd

        if configured:
            selector = int(configured) if configured.isdigit() else configured
            dev = sd.query_devices(selector)
            return f"{configured} -> {dev['name']}"

        default_in = sd.default.device[0]
        dev = sd.query_devices(default_in)
        return f"default {default_in} -> {dev['name']}"
    except Exception as exc:
        return f"unknown ({exc})"


def _run_text_mode():
    print("\n" + "=" * 40, flush=True)
    print("  进入纯文本指令模式", flush=True)
    print("  可用指令: [文本内容] | #反馈 | exit", flush=True)
    print("=" * 40 + "\n", flush=True)
    while True:
        try:
            user_input = input("你: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                break
            input_queue.put(EngineEvent(EventType.TEXT_IN, user_input))
            time.sleep(0.1)
        except EOFError:
            break


def _run_voice_mode(engine: MainEngine, once: bool):
    cfg = get_settings()
    arm_delay = cfg.speech.asr_timing.arm_delay_sec
    post_arm_guard = cfg.speech.asr_timing.post_arm_guard_sec
    print("\n" + "=" * 40, flush=True)
    print("  进入语音交互模式 (VAD)", flush=True)
    if once:
        print("  单轮验收模式：完成一轮识别和播报后自动退出", flush=True)
    else:
        print("  请直接说话，按 Ctrl+C 退出", flush=True)
    print(f"  麦克风将在 {arm_delay:.1f} 秒后开始监听", flush=True)
    print(f"  麦克风稳定期 {post_arm_guard:.1f} 秒，结束后再开始识别", flush=True)
    print(f"  当前输入设备: {_describe_input_device()}", flush=True)
    print('  看到日志 "microphone is armed, please speak now" 后再开始说话', flush=True)
    print("=" * 40 + "\n", flush=True)

    arm_wait = max(arm_delay + post_arm_guard + 3.0, 5.0)
    if engine.wait_until_armed(arm_wait):
        print("[Voice] 麦克风已开始监听，现在可以说话。", flush=True)
    elif engine.should_stop():
        print(
            "[Voice] 语音链路在开始监听前已经退出，请查看上方日志里的 stop requested 原因。",
            flush=True,
        )
    else:
        print("[Voice] 麦克风尚未就绪，请查看上方日志继续排查。", flush=True)

    while not engine.should_stop():
        time.sleep(0.2)


def main():
    ap = argparse.ArgumentParser(description="MoniBox-KB edge runtime")
    ap.add_argument("--mode", choices=["mic_vad", "text"], default="mic_vad")
    ap.add_argument(
        "--profile",
        choices=_PROFILE_CHOICES,
        default=None,
        help=(
            "Runtime profile to load (from profiles/*.yaml). "
            "Overrides RUNTIME_PROFILE env var. Defaults to base.yaml if omitted."
        ),
    )
    ap.add_argument(
        "--once",
        action="store_true",
        help="Stop after one handled turn in mic_vad mode",
    )
    args = ap.parse_args()

    # 命令行 --profile 优先级高于环境变量
    if args.profile:
        os.environ["RUNTIME_PROFILE"] = args.profile
        print(f"[Config] Using profile: {args.profile}", flush=True)

    engine = MainEngine(
        mode=args.mode, max_turns=1 if args.once and args.mode == "mic_vad" else 0
    )

    try:
        engine.start()
        if args.mode == "text":
            _run_text_mode()
        else:
            _run_voice_mode(engine, once=args.once)
    except KeyboardInterrupt:
        print("\n[User] 收到中断信号", flush=True)
    except Exception:
        logger.exception("RuntimeEdge fatal error")
    finally:
        engine.stop()
        print("系统已安全关闭。", flush=True)


if __name__ == "__main__":
    main()
