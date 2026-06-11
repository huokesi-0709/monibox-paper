from __future__ import annotations

import contextlib
import queue
import threading
from dataclasses import dataclass

import pyttsx3
from comtypes import CoInitialize, CoUninitialize


@dataclass
class _TTSItem:
    text: str
    done: threading.Event
    style: str | None = None


class Pyttsx3TTS:
    """
    稳定版 pyttsx3 TTS：
    - 单 worker 线程串行播放，避免多轮调用卡死/丢声
    - worker 线程显式 COM 初始化（Windows SAPI 必需，解决“只播一次”）
    """

    def __init__(
        self, rate: int = 180, volume: float = 1.0, voice_name_contains: str = ""
    ):
        self._rate = int(rate)
        self._volume = float(volume)
        self._voice_name_contains = voice_name_contains

        self._q: queue.Queue[_TTSItem | None] = queue.Queue()
        self._speaking = threading.Event()

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def speak(
        self,
        text: str,
        block: bool = True,
        style: str | None = None,
        metadata: dict | None = None,
    ):
        t = (text or "").strip()
        if not t:
            return
        done = threading.Event()
        self._q.put(_TTSItem(t, done, style))
        if block:
            done.wait()

    def close(self):
        self._q.put(None)

    def _init_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", self._rate)
        engine.setProperty("volume", self._volume)

        if self._voice_name_contains:
            try:
                for v in engine.getProperty("voices"):
                    if self._voice_name_contains.lower() in (v.name or "").lower():
                        engine.setProperty("voice", v.id)
                        break
            except Exception:
                pass
        return engine

    def _style_props(self, style: str | None) -> tuple[int, float]:
        rate = self._rate
        volume = self._volume
        normalized = (style or "").lower()
        if "urgent" in normalized:
            rate += 25
            volume += 0.06
        elif "warm" in normalized:
            rate -= 15
            volume += 0.02
        elif "calm" in normalized:
            rate -= 10
        return rate, min(1.0, max(0.0, volume))

    def _worker(self):
        CoInitialize()
        try:
            engine = self._init_engine()

            while True:
                item = self._q.get()
                if item is None:
                    break

                self._speaking.set()
                try:
                    with contextlib.suppress(Exception):
                        engine.stop()

                    rate, volume = self._style_props(item.style)
                    engine.setProperty("rate", rate)
                    engine.setProperty("volume", volume)
                    engine.say(item.text)
                    engine.runAndWait()

                except Exception:
                    # 出错就重建 engine
                    with contextlib.suppress(Exception):
                        engine = self._init_engine()
                finally:
                    self._speaking.clear()
                    item.done.set()
        finally:
            CoUninitialize()
