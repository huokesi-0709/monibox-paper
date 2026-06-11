"""
Main runtime coordinator for text and mic_vad modes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime

from monibox.config import settings
from monibox.core_loop.shared import (
    EngineEvent,
    EventType,
    clear_runtime_queues,
    get_runtime_trace_logger,
    input_queue,
    new_interaction_id,
    output_queue,
)
from monibox.core_loop.resources import global_resources
from monibox.runtime.slot_parser import parse_location, parse_yesno
from monibox.runtime.orchestrator import MoniSession, SessionConfig

logger = logging.getLogger(__name__)


def _resolve_input_device() -> int | str | None:
    raw = (os.getenv("REC_INPUT_DEVICE") or os.getenv("REC_DEVICE") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


class MainEngine:
    def __init__(self, mode: str = "mic_vad", max_turns: int = 0):
        self.mode = mode
        self.max_turns = max(0, int(max_turns))

        self.session: MoniSession | None = None
        self.player_thread = None
        self.asr_thread = None
        self._session_thread: threading.Thread | None = None
        self._coord_thread: threading.Thread | None = None

        self._stop_event = threading.Event()
        self._shutdown_when_idle = False
        self._handled_turns = 0
        self._armed_at: float | None = None
        self._trace = get_runtime_trace_logger()
        self._last_asr_paused: bool | None = None

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def wait_until_armed(self, timeout_sec: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_sec))
        while time.monotonic() < deadline:
            if (
                self.asr_thread
                and getattr(self.asr_thread, "is_armed", lambda: False)()
            ):
                return True
            if self._stop_event.is_set():
                return False
            time.sleep(0.05)
        return bool(
            self.asr_thread and getattr(self.asr_thread, "is_armed", lambda: False)()
        )

    def _request_stop(self, reason: str = "manual"):
        if self._stop_event.is_set():
            return
        logger.info(f"[MainEngine] stop requested: {reason}")
        self._trace.log("engine_stop_requested", reason=reason)
        self._stop_event.set()
        input_queue.put(EngineEvent(EventType.SYS_CTRL, "exit"))

    @staticmethod
    def _has_rescue_signal(text: str) -> bool:
        hints = (
            "流血",
            "出血",
            "血",
            "腿",
            "手",
            "脚",
            "头",
            "胸",
            "脖子",
            "疼",
            "痛",
            "喘",
            "呼吸",
            "咳",
            "晕",
            "发黑",
            "冷",
            "抖",
            "怕",
            "慌",
            "晃",
            "压住",
            "少了点",
            "还在",
            "没有",
            "有",
        )
        return any(hint in text for hint in hints)

    @staticmethod
    def _looks_repetitive_noise(text: str) -> bool:
        compact = re.sub(r"[，。！？、,\s]+", "", (text or "").strip())
        if len(compact) < 18:
            return False

        for size in range(4, 11):
            seen = set()
            for idx in range(len(compact) - size + 1):
                part = compact[idx : idx + size]
                if part in seen:
                    continue
                seen.add(part)
                count = compact.count(part)
                if count >= 3 and count * size >= int(len(compact) * 0.45):
                    return True
        return False

    def _ignore_reason_for_asr_text(self, text: str, metadata: dict) -> str | None:
        if metadata.get("source") != "asr" or not self.session:
            return None

        t = (text or "").strip()
        if not t:
            return "empty_asr_text"

        if self._looks_repetitive_noise(t):
            logger.info("[MainEngine] ignored repetitive ASR noise: %s", t[:60])
            return "repetitive_noise"

        pending = getattr(self.session, "proto_handler", None)
        pending = getattr(pending, "pending_protocol", None)
        if not isinstance(pending, dict):
            return None

        slot = str(pending.get("slot") or "")
        if (
            slot == "location"
            and parse_location(t) is None
            and len(t) > 8
            and not self._has_rescue_signal(t)
        ):
            logger.info(
                "[MainEngine] ignored unrelated ASR while waiting for location: %s",
                t[:60],
            )
            return "pending_location_unrelated"
        if (
            slot == "yesno"
            and parse_yesno(t) is None
            and len(t) > 8
            and not self._has_rescue_signal(t)
        ):
            logger.info(
                "[MainEngine] ignored unrelated ASR while waiting for yes/no: %s",
                t[:60],
            )
            return "pending_yesno_unrelated"

        return None

    def _session_loop(self):
        logger.info("[MainEngine] Session loop started")
        self._trace.log("engine_session_loop_started", mode=self.mode)
        while not self._stop_event.is_set():
            try:
                event = input_queue.get(timeout=1.0)
            except Exception:
                continue

            if event.event_type == EventType.SYS_CTRL and event.data == "exit":
                break

            if event.event_type != EventType.TEXT_IN:
                continue

            user_text = str(event.data or "")
            metadata = dict(event.metadata or {})
            interaction_id = str(
                metadata.get("interaction_id")
                or new_interaction_id(metadata.get("source", "text"))
            )
            metadata["interaction_id"] = interaction_id
            source = str(metadata.get("source") or "text")
            self._trace.log(
                "text_in",
                interaction_id=interaction_id,
                source=source,
                text=user_text,
                events=metadata.get("events"),
            )

            ignore_reason = self._ignore_reason_for_asr_text(user_text, metadata)
            if ignore_reason:
                self._trace.log(
                    "text_ignored",
                    interaction_id=interaction_id,
                    source=source,
                    reason=ignore_reason,
                    text=user_text,
                )
                continue
            if user_text.strip() in ("#反馈", "#差评", "#评分"):
                self._handle_feedback("#差评")
                continue

            try:
                if self.asr_thread:
                    self.asr_thread.paused = True
                if self.session:
                    self.session.current_interaction_id = interaction_id
                    self.session.output.set_turn_context(
                        {"interaction_id": interaction_id, "input_source": source}
                    )
                reply = self.session.handle(
                    user_text, events=metadata.get("events", [])
                )
                print(f"[Reply] {reply}", flush=True)
                logger.info(f"[MainEngine] Session Reply: {reply}")
                trace_info = dict(getattr(self.session, "last_trace", {}) or {})
                self._trace.log(
                    "reply_ready",
                    interaction_id=interaction_id,
                    source=source,
                    reply=reply,
                    session_trace=trace_info,
                )
            except Exception as e:
                logger.error(f"[MainEngine] Session handle failed: {e}")
                self._trace.log(
                    "reply_error", interaction_id=interaction_id, error=str(e)
                )
                continue
            finally:
                if self.session:
                    self.session.current_interaction_id = None
                    self.session.output.set_turn_context({})

            self._handled_turns += 1
            if self.max_turns and self._handled_turns >= self.max_turns:
                logger.info(
                    "[MainEngine] one-shot target reached, waiting for playback to finish"
                )
                self._shutdown_when_idle = True
                if self.asr_thread:
                    self.asr_thread.paused = True

    def _handle_feedback(self, label: str):
        history = self.session.mem.items
        feedback_path = os.path.join(os.getcwd(), "build", "feedback_logs.jsonl")
        os.makedirs(os.path.dirname(feedback_path), exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "label": label,
            "recent_history": [str(it) for it in history[-5:]],
        }
        with open(feedback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.warning(f"[MainEngine] Feedback recorded: {label}")

    def _audio_busy(self) -> bool:
        queue_busy = not output_queue.empty()
        player_busy = bool(
            self.player_thread
            and getattr(self.player_thread, "is_playing", lambda: False)()
        )
        return queue_busy or player_busy

    def _coordination_loop(self):
        while not self._stop_event.is_set():
            if self.asr_thread and self._armed_at is None:
                if getattr(self.asr_thread, "is_armed", lambda: False)():
                    self._armed_at = time.monotonic()
                    logger.info("[MainEngine] microphone armed and ready")

            audio_busy = self._audio_busy()

            if self.asr_thread:
                if self._shutdown_when_idle or audio_busy:
                    self.asr_thread.paused = True
                else:
                    time.sleep(0.3)
                    if not self._audio_busy():
                        self.asr_thread.paused = False

                paused_now = bool(self.asr_thread.paused)
                if self._last_asr_paused is None or paused_now != self._last_asr_paused:
                    self._last_asr_paused = paused_now
                    self._trace.log(
                        "asr_state", state="paused" if paused_now else "listening"
                    )

            ready_to_finish = (
                self._shutdown_when_idle
                and self.max_turns > 0
                and self._handled_turns >= self.max_turns
            )
            if ready_to_finish and not audio_busy:
                time.sleep(0.2)
                if not self._audio_busy():
                    self._request_stop("one-shot turn completed")
                    break

            time.sleep(0.1)

    def start(self):
        dropped = clear_runtime_queues()
        self._trace.log("engine_start", mode=self.mode, max_turns=self.max_turns)
        if any(dropped.values()):
            logger.warning(
                "[MainEngine] cleared stale runtime events before start: "
                f"input={dropped['input']}, audio_in={dropped['audio_in']}, output={dropped['output']}"
            )

        try:
            print("[MainEngine] 启动全局资源预加载...")
            global_resources.initialize_all(
                rag_db_path=settings.rag_db_path,
                enable_asr=(self.mode != "text"),
                enable_tts=(self.mode != "text"),
                preload_embedding=(self.mode != "text"),
            )
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"[MainEngine] Resource initialization failed: {e}")
            raise

        tts = global_resources.get_tts()
        if tts and self.mode != "text":
            tts._playback_mode = "queue"

        sess_cfg = SessionConfig(
            llm_path=os.getenv("LLM_GGUF_PATH", ""), tts_enabled=(self.mode != "text")
        )
        self.session = MoniSession(
            settings.rag_db_path,
            sess_cfg,
            rag=global_resources.get_rag(),
            llm=global_resources.get_llm(),
            tts=global_resources.get_tts(),
        )
        time.sleep(0.5)

        self._session_thread = threading.Thread(target=self._session_loop, daemon=True)
        self._session_thread.start()

        if self.mode == "text":
            logger.info("[MainEngine] text mode started without ASR/TTS worker threads")
            logger.info(f"[MainEngine] system started. mode={self.mode}")
            return

        from monibox.asr.worker import ASRWorkerThread
        from monibox.audio.vad import VadConfig
        from monibox.hw.player import AudioPlayerThread

        self.player_thread = AudioPlayerThread()
        self.player_thread.start()

        sr = int(os.getenv("REC_SAMPLE_RATE", "16000"))
        vad_cfg = VadConfig(
            sample_rate=sr,
            start_rms=float(os.getenv("VAD_START_RMS", "0.006")),
            end_rms=(
                float(os.getenv("VAD_END_RMS")) if os.getenv("VAD_END_RMS") else 0.0065
            ),
            min_record_ms=int(os.getenv("VAD_MIN_RECORD_MS", "500")),
            end_silence_ms=int(os.getenv("VAD_END_SIL_MS", "800")),
            max_seconds=float(os.getenv("VAD_MAX_SEC", "12")),
            pre_roll_ms=int(os.getenv("VAD_PRE_ROLL_MS", "400")),
            device=_resolve_input_device(),
        )
        arm_delay = float(os.getenv("ASR_ARM_DELAY_SEC", "1.5"))
        post_arm_guard = float(os.getenv("ASR_POST_ARM_GUARD_SEC", "2.0"))
        self.asr_thread = ASRWorkerThread(
            vad_cfg=vad_cfg, arm_delay_sec=arm_delay, post_arm_guard_sec=post_arm_guard
        )
        self.asr_thread.start()

        self._coord_thread = threading.Thread(
            target=self._coordination_loop, daemon=True
        )
        self._coord_thread.start()

        logger.info(f"[MainEngine] full voice chain started. mode={self.mode}")
        self._trace.log("engine_voice_chain_started", mode=self.mode)

    def stop(self):
        logger.info("[MainEngine] shutting down...")
        self._request_stop("shutdown")

        if self.asr_thread:
            self.asr_thread.stop()
        if self.player_thread:
            self.player_thread.stop()

        if self._session_thread:
            self._session_thread.join(timeout=2)
        if self.player_thread:
            self.player_thread.join(timeout=2)
        if self._coord_thread:
            self._coord_thread.join(timeout=2)

        dropped = clear_runtime_queues()
        if any(dropped.values()):
            logger.info(
                "[MainEngine] cleared runtime queues on stop: "
                f"input={dropped['input']}, audio_in={dropped['audio_in']}, output={dropped['output']}"
            )

        logger.info("[MainEngine] shutdown complete")
        self._trace.log("engine_stopped", mode=self.mode)
