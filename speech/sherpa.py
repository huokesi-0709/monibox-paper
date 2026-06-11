"""
speech/sherpa.py

用途
-----
基于 sherpa-onnx 的高质量离线 TTS 引擎，支持 MeloTTS（高质量）和 Piper（低延迟）两类中文模型。
专为 Radxa Zero 3W (ARM aarch64) 等边缘设备设计。

设计决策
--------
- 单 Worker 线程串行播放，避免 ONNX 推理占满 CPU，与现有 SapiTTS 架构保持一致
- LRU 音频缓存：对高频短句缓存合成结果，第二次播放零延迟
- sounddevice 播放：轻量、跨平台，项目已有依赖
- 推理线程数限制：通过 sherpa-onnx 的 num_threads 参数限制，默认 2 线程
"""

from __future__ import annotations

import hashlib
import logging
import queue
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class _TTSItem:
    text: str
    done: threading.Event
    speed: float = 1.0
    sid: int = 0
    volume_gain: float = 1.0
    cache_key: str = ""
    metadata: dict | None = None


@dataclass(frozen=True)
class _StyleProfile:
    speed_mult: float = 1.0
    volume_gain: float = 1.0
    sid: int | None = None


DEFAULT_STYLE_PROFILES = {
    "default": _StyleProfile(),
    "calm": _StyleProfile(speed_mult=0.96, volume_gain=0.98),
    "warm": _StyleProfile(speed_mult=0.93, volume_gain=1.00),
    "urgent": _StyleProfile(speed_mult=1.18, volume_gain=1.08),
    "urgent_calm": _StyleProfile(speed_mult=1.08, volume_gain=1.03),
}


class SherpaTTS:
    """
    sherpa-onnx TTS 引擎封装，统一支持 MeloTTS 和 Piper 模型。

    与 SapiTTS / Pyttsx3TTS 接口完全兼容：
    - speak(text, block=True)  阻塞式播放
    - close()                  关闭 Worker 线程
    """

    def __init__(
        self,
        model_dir: str,
        model_type: str = "melo",
        num_threads: int = 2,
        cache_size: int = 100,
        speed: float = 1.0,
        sid: int = 0,
        noise_scale: float = 0.667,
        noise_scale_w: float = 0.8,
        playback_mode: str = "queue",  # "queue" 不直接出声音，而是放进消息队列; "sync" 同步发脾气
    ):
        """
        初始化 sherpa-onnx TTS 引擎。

        @param model_dir 模型目录路径（如 models/tts/sherpa/vits-melo-tts-zh_en）
        @param model_type 模型类型，"melo" 或 "piper"
        @param num_threads ONNX 推理线程数（限制 CPU 占用）
        @param cache_size LRU 缓存最大条目数（0 禁用缓存）
        @param speed 语速系数，1.0 为默认语速
        @param sid 说话人 ID（多说话人模型用）
        """
        self._model_dir = Path(model_dir)
        self._model_type = model_type.strip().lower()
        self._num_threads = num_threads
        self._speed = speed
        self._sid = sid
        self._noise_scale = noise_scale
        self._noise_scale_w = noise_scale_w
        self._playback_mode = playback_mode

        # NOTE: LRU 缓存：key=文本哈希, value=(samples, sample_rate)
        self._cache: OrderedDict[str, tuple[np.ndarray, int]] = OrderedDict()
        self._cache_size = max(0, cache_size)

        self._q: queue.Queue[_TTSItem | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def speak(
        self,
        text: str,
        block: bool = True,
        style: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        合成并播放文本。

        @param text 要合成的文本
        @param block 是否阻塞等待播放完成
        @param style 风格标记，用于驱动语速/音量/音色 profile
        """
        t = (text or "").strip()
        if not t:
            return

        profile = self._resolve_style_profile(style)
        speed = min(2.0, max(0.5, self._speed * profile.speed_mult))
        sid = self._sid if profile.sid is None else profile.sid
        volume_gain = min(1.3, max(0.7, profile.volume_gain))
        cache_key = self._text_hash(f"{t}|{speed:.3f}|{sid}|{volume_gain:.3f}")

        done = threading.Event()
        self._q.put(
            _TTSItem(t, done, speed, sid, volume_gain, cache_key, dict(metadata or {}))
        )
        if block:
            done.wait()

    def close(self) -> None:
        """关闭 Worker 线程"""
        self._q.put(None)

    def _build_tts_engine(self):
        """
        构建 sherpa-onnx OfflineTts 实例。
        延迟到 Worker 线程中调用，避免主线程阻塞。
        """
        import shutil

        import sherpa_onnx

        # NOTE: 绕过 onnxruntime 在 Windows 下存在中文路径加载失败的 bug (No graph was found in the protobuf)
        # 如果路径包含非 ASCII 字符，则将整个模型目录镜像到用户目录下。
        model_dir_str = str(self._model_dir)
        if not model_dir_str.isascii():
            try:
                cache_dir = (
                    Path.home() / ".cache" / "monibox_tts" / self._model_dir.name
                )
                if not cache_dir.exists():
                    logger.info(
                        "检测到中文路径，为兼容 sherpa-onnx ，正将模型复制到: %s",
                        cache_dir,
                    )
                    cache_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(self._model_dir, cache_dir)
                else:
                    logger.debug("使用无中文路径缓存: %s", cache_dir)
                self._model_dir = cache_dir
            except Exception as e:
                logger.warning(
                    "模型因中文路径尝试复制到缓存目录失败: %s. 可能导致 TTS 无法加载。",
                    e,
                )

        model_path = self._model_dir / "model.onnx"
        tokens_path = self._model_dir / "tokens.txt"

        if not model_path.exists():
            raise FileNotFoundError(f"TTS 模型文件不存在: {model_path}")
        if not tokens_path.exists():
            raise FileNotFoundError(f"TTS tokens 文件不存在: {tokens_path}")

        if self._model_type == "melo":
            # MeloTTS 模型需要 lexicon.txt 和分词词典
            lexicon_path = self._model_dir / "lexicon.txt"
            dict_dir = self._model_dir / "dict"

            # NOTE: 构建 rule FSTs 路径列表（日期/数字格式化）
            rule_fsts = []
            for fst_name in ["date.fst", "number.fst", "phone.fst"]:
                fst_path = self._model_dir / fst_name
                if fst_path.exists():
                    rule_fsts.append(str(fst_path))

            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=str(model_path),
                        lexicon=str(lexicon_path) if lexicon_path.exists() else "",
                        tokens=str(tokens_path),
                        dict_dir=str(dict_dir) if dict_dir.exists() else "",
                        noise_scale=self._noise_scale,
                        noise_scale_w=self._noise_scale_w,
                    ),
                    num_threads=self._num_threads,
                    debug=False,
                ),
                rule_fsts=",".join(rule_fsts) if rule_fsts else "",
            )
        else:
            # Piper 模型：只需 model.onnx + tokens.txt
            data_dir = self._model_dir / "espeak-ng-data"
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=str(model_path),
                        tokens=str(tokens_path),
                        data_dir=str(data_dir) if data_dir.exists() else "",
                        noise_scale=self._noise_scale,
                        noise_scale_w=self._noise_scale_w,
                    ),
                    num_threads=self._num_threads,
                    debug=False,
                )
            )

        tts = sherpa_onnx.OfflineTts(tts_config)
        logger.info(
            "sherpa-onnx TTS 引擎已加载: model_type=%s, model_dir=%s, threads=%d",
            self._model_type,
            self._model_dir,
            self._num_threads,
        )
        return tts

    @staticmethod
    def _text_hash(raw: str) -> str:
        """生成短哈希作为缓存键。"""
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    def _resolve_style_profile(self, style: str | None) -> _StyleProfile:
        """把 style 字符串映射成真实的 TTS profile。"""
        normalized = (style or "").strip().lower()
        if not normalized:
            return DEFAULT_STYLE_PROFILES["default"]
        if normalized in DEFAULT_STYLE_PROFILES:
            return DEFAULT_STYLE_PROFILES[normalized]

        merged = DEFAULT_STYLE_PROFILES["default"]
        for token in re.split(r"[_\-\s]+", normalized):
            profile = DEFAULT_STYLE_PROFILES.get(token)
            if profile is None:
                continue
            merged = _StyleProfile(
                speed_mult=merged.speed_mult * profile.speed_mult,
                volume_gain=merged.volume_gain * profile.volume_gain,
                sid=profile.sid if profile.sid is not None else merged.sid,
            )
        return merged

    def _cache_get(self, key: str) -> tuple[np.ndarray, int] | None:
        """从 LRU 缓存获取音频数据"""
        if key in self._cache:
            # NOTE: 移动到末尾表示最近访问
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: str, samples: np.ndarray, sample_rate: int) -> None:
        """写入 LRU 缓存"""
        if self._cache_size <= 0:
            return
        self._cache[key] = (samples, sample_rate)
        # 超出容量时淘汰最旧条目
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _play_audio(
        self, samples: np.ndarray, sample_rate: int, metadata: dict | None = None
    ) -> None:
        """根据模式，推给队列或者阻塞式播放"""
        if self._playback_mode == "queue":
            from core.shared import EngineEvent, EventType, output_queue

            output_queue.put(
                EngineEvent(
                    event_type=EventType.TTS_CHUNK,
                    data={"samples": samples, "sample_rate": sample_rate},
                    metadata=dict(metadata or {}),
                )
            )
        else:
            try:
                import sounddevice as sd

                sd.play(samples, samplerate=sample_rate)
                sd.wait()
            except Exception as e:
                logger.error("音频播放失败: %s", e)

    def _worker(self) -> None:
        """Worker 线程：串行处理合成和播放请求"""
        try:
            tts_engine = self._build_tts_engine()
        except Exception as e:
            logger.error("sherpa-onnx TTS 引擎加载失败: %s", e)
            # 引擎加载失败后，持续消费队列但不播放，避免调用方永久阻塞
            while True:
                item = self._q.get()
                if item is None:
                    break
                item.done.set()
            return

        while True:
            item = self._q.get()
            if item is None:
                break

            try:
                cache_key = item.cache_key or self._text_hash(item.text)
                cached = self._cache_get(cache_key)

                if cached is not None:
                    # 缓存命中，直接播放
                    logger.debug("[TTS 缓存命中] %s", item.text[:20])
                    self._play_audio(cached[0], cached[1], metadata=item.metadata)
                else:
                    # 缓存未命中，执行合成
                    logger.debug("[TTS 合成] %s", item.text[:20])
                    audio = tts_engine.generate(
                        item.text, sid=item.sid, speed=item.speed
                    )

                    if audio.samples:
                        samples = np.array(audio.samples, dtype=np.float32)
                        if item.volume_gain != 1.0:
                            samples = np.clip(samples * item.volume_gain, -1.0, 1.0)
                        self._cache_put(cache_key, samples, audio.sample_rate)
                        self._play_audio(
                            samples, audio.sample_rate, metadata=item.metadata
                        )
                    else:
                        logger.warning("TTS 合成返回空音频: %s", item.text[:30])

            except Exception as e:
                logger.error("TTS 合成/播放异常: %s", e)
            finally:
                item.done.set()
