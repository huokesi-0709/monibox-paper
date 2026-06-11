"""
ASR worker thread for mic_vad mode.
"""

from __future__ import annotations

import logging
import threading
import time

from monibox.audio.vad_recorder import VadConfig, record_vad
from monibox.core_loop.base import (
    EngineEvent,
    EventType,
    get_runtime_trace_logger,
    input_queue,
    new_interaction_id,
)
from monibox.core_loop.resource_manager import global_resources

logger = logging.getLogger(__name__)


class ASRWorkerThread(threading.Thread):
    def __init__(
        self,
        vad_cfg: VadConfig | None = None,
        arm_delay_sec: float = 0.0,
        post_arm_guard_sec: float = 0.0,
    ):
        super().__init__(daemon=True)
        self.vad_cfg = vad_cfg or VadConfig()
        self.arm_delay_sec = max(0.0, float(arm_delay_sec))
        self.post_arm_guard_sec = max(0.0, float(post_arm_guard_sec))
        self.paused = False

        self._stop_event = threading.Event()
        self._armed_event = threading.Event()
        self._trace = get_runtime_trace_logger()

    def is_armed(self) -> bool:
        return self._armed_event.is_set()

    def run(self):
        logger.info("[ASRWorker] worker thread started")
        asr = global_resources.get_asr()
        if not asr:
            logger.error("[ASRWorker] no ASR engine in global resources")
            return

        if self.arm_delay_sec > 0:
            logger.info(
                f"[ASRWorker] arming microphone in {self.arm_delay_sec:.1f}s..."
            )
            deadline = time.monotonic() + self.arm_delay_sec
            while not self._stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)

        if self._stop_event.is_set():
            return

        if self.post_arm_guard_sec > 0:
            logger.info(
                f"[ASRWorker] stabilizing microphone for {self.post_arm_guard_sec:.1f}s..."
            )
            deadline = time.monotonic() + self.post_arm_guard_sec
            while not self._stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)

        if self._stop_event.is_set():
            return

        self._armed_event.set()
        logger.info("[ASRWorker] microphone is armed, please speak now")
        self._trace.log("asr_armed")

        while not self._stop_event.is_set():
            if self.paused:
                time.sleep(0.2)
                continue

            try:
                audio = record_vad(self.vad_cfg)
                if audio is None or self.paused:
                    continue

                audio_sec = len(audio) / float(self.vad_cfg.sample_rate)
                print(
                    f"[ASR] 已捕获语音片段，时长约 {audio_sec:.2f}s，开始识别...",
                    flush=True,
                )
                t1 = time.time()
                text = asr.transcribe(audio)
                t2 = time.time()

                if text:
                    interaction_id = new_interaction_id("asr")
                    # 一旦拿到有效文本，立刻暂停下一轮录音，等主协调线程
                    # 在回复/播放完成后再决定是否恢复，避免 one-shot 和播报前
                    # 的短时间窗口里又抢先录到一段无意义音频。
                    self.paused = True
                    print(f"[ASR] 识别结果: {text}", flush=True)
                    logger.info(f"[ASRWorker] transcribed ({t2 - t1:.2f}s): {text}")
                    self._trace.log(
                        "asr_text",
                        interaction_id=interaction_id,
                        source="asr",
                        duration_sec=round(audio_sec, 2),
                        transcribe_sec=round(t2 - t1, 2),
                        text=text,
                    )
                    input_queue.put(
                        EngineEvent(
                            EventType.TEXT_IN,
                            text,
                            metadata={
                                "source": "asr",
                                "interaction_id": interaction_id,
                            },
                        )
                    )
                else:
                    print("[ASR] 未识别到有效文本，继续监听。", flush=True)
                    self._trace.log("asr_empty", duration_sec=round(audio_sec, 2))
            except Exception as e:
                logger.error(f"[ASRWorker] record/transcribe failed: {e}")
                self._trace.log("asr_error", error=str(e))
                time.sleep(1.0)

    def stop(self):
        self._stop_event.set()
