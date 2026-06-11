from __future__ import annotations

import contextlib
import os
import queue
import threading
from dataclasses import dataclass

import pythoncom
import win32com.client


@dataclass
class _TTSItem:
    text: str
    done: threading.Event
    style: str | None = None


class SapiTTS:
    """
    Windows SAPI TTS（稳定阻塞版）
    - speak(block=True) 会尽量等到真正播完才返回
    - 若超过最大播放时长才强制中止（防卡死）
    """

    def __init__(self, rate: int = 0, volume: int = 100):
        self._rate = int(rate)
        self._volume = int(volume)

        # 单次 WaitUntilDone 轮询间隔（ms）
        self._poll_ms = int(os.getenv("TTS_POLL_MS", "200"))
        # 最长允许播放秒数（超出认为卡死/过长，才会 purge）
        self._max_play_sec = float(os.getenv("TTS_MAX_PLAY_SEC", "25"))

        self._q: queue.Queue[_TTSItem | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

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

        # 标点符号轻微停顿处理（用逗号或句号替换一部分连续顿号/空格，利用 SAPI 自带法则停顿）
        t = t.replace("、", "，")

        done = threading.Event()
        self._q.put(_TTSItem(t, done, style))
        if block:
            # 主线程等到 worker 宣告完成（通常是播完）
            done.wait(timeout=self._max_play_sec + 2.0)

    def close(self):
        self._q.put(None)

    def _new_voice(self):
        v = win32com.client.Dispatch("SAPI.SpVoice")
        v.Rate = self._rate
        v.Volume = self._volume
        return v

    def _worker(self):
        pythoncom.CoInitialize()
        try:
            voice = self._new_voice()

            while True:
                item = self._q.get()
                if item is None:
                    break

                try:
                    # 动态调整语速
                    style = (item.style or "").lower()
                    if "urgent" in style:
                        voice.Rate = min(10, self._rate + 2)
                        voice.Volume = min(100, self._volume + 8)
                    elif "warm" in style:
                        voice.Rate = max(-10, self._rate - 1)
                        voice.Volume = min(100, self._volume + 3)
                    elif "calm" in style:
                        voice.Rate = max(-10, self._rate - 1)
                        voice.Volume = self._volume
                    else:
                        voice.Rate = self._rate
                        voice.Volume = self._volume

                    # 1 = SVSFlagsAsync：异步说，但我们用 WaitUntilDone 等到播完
                    voice.Speak(item.text, 1)

                    waited = 0.0
                    while True:
                        ok = voice.WaitUntilDone(self._poll_ms)
                        if ok:
                            break
                        waited += self._poll_ms / 1000.0
                        if waited >= self._max_play_sec:
                            # 超过上限才 purge（避免长句被提前掐断）
                            try:
                                voice.Speak("", 2)  # 2 = SVSFPurgeBeforeSpeak
                            except Exception:
                                pass
                            voice = self._new_voice()
                            break

                except Exception:
                    # 出错则重建 voice，避免后续全部失声
                    with contextlib.suppress(Exception):
                        voice = self._new_voice()
                finally:
                    item.done.set()

        finally:
            pythoncom.CoUninitialize()
