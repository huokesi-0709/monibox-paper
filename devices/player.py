"""
Audio playback worker for queued TTS chunks.
"""

from __future__ import annotations

import logging
import threading
from queue import Empty

import sounddevice as sd

from core.shared import (
    EventType,
    get_runtime_trace_logger,
    output_queue,
)

logger = logging.getLogger(__name__)


class AudioPlayerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._playing_event = threading.Event()
        self._trace = get_runtime_trace_logger()

    def is_playing(self) -> bool:
        return self._playing_event.is_set()

    def run(self):
        logger.info("[AudioPlayer] playback thread started")
        while not self._stop_event.is_set():
            try:
                event = output_queue.get(timeout=0.5)
            except Empty:
                continue

            if event.event_type == EventType.TTS_CHUNK:
                meta = event.metadata or {}
                interaction_id = meta.get("interaction_id")
                try:
                    samples = event.data["samples"]
                    sample_rate = event.data["sample_rate"]
                    self._playing_event.set()
                    self._trace.log(
                        "tts_playback_start",
                        interaction_id=interaction_id,
                        sample_rate=sample_rate,
                        sample_count=len(samples),
                        tts_text=meta.get("tts_text"),
                        style=meta.get("tts_style"),
                    )
                    sd.play(samples, samplerate=sample_rate)
                    sd.wait()
                except Exception as e:
                    logger.error(f"[AudioPlayer] playback error: {e}")
                    self._trace.log(
                        "tts_playback_error",
                        interaction_id=interaction_id,
                        error=str(e),
                    )
                finally:
                    self._playing_event.clear()
                    self._trace.log("tts_playback_done", interaction_id=interaction_id)
            elif event.event_type == EventType.SYS_CTRL and event.data == "exit":
                logger.info("[AudioPlayer] received exit signal")
                break

    def stop(self):
        self._stop_event.set()
