from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from faster_whisper import WhisperModel

from runtime.input_normalizer import InputNormalizer

DEFAULT_RESCUE_INITIAL_PROMPT = (
    "这是中文灾害救援对话。常见词：腿、手、胳膊、头、脑袋、流血、伤口、骨折、"
    "喘不过气、呼吸困难、咳嗽、余震、头晕发黑、好冷发抖、被压住、救命。"
)

ASR_JUNK_HINTS = (
    "点赞",
    "订阅",
    "转发",
    "打赏",
    "明镜",
    "栏目",
    "节目",
    "关注",
    "片尾",
    "欢迎收看",
    "谢谢观看",
)


def build_default_initial_prompt(extra: str = "") -> str:
    prompt = DEFAULT_RESCUE_INITIAL_PROMPT
    extra = (extra or "").strip()
    if extra:
        prompt = f"{prompt} {extra}"
    return prompt


def _has_repeated_long_chunk(text: str, min_len: int = 6, min_repeats: int = 3) -> bool:
    t = (text or "").strip()
    if len(t) < min_len * min_repeats:
        return False

    for size in range(min_len, min(18, len(t) // 2 + 1)):
        counts: dict[str, int] = {}
        for i in range(len(t) - size + 1):
            chunk = t[i : i + size]
            if any(ch.isspace() for ch in chunk):
                continue
            counts[chunk] = counts.get(chunk, 0) + 1
            if counts[chunk] >= min_repeats:
                return True
    return False


def is_probable_junk_transcript(text: str) -> bool:
    """
    过滤环境噪音触发的 Whisper 幻听长串文本。
    当前重点拦截：宣传口播、栏目结尾词、重复刷屏式文本。
    """
    t = (text or "").strip()
    if not t:
        return False

    hint_hits = sum(1 for hint in ASR_JUNK_HINTS if hint in t)
    if hint_hits >= 2:
        return True

    if hint_hits >= 1 and len(t) >= 20:
        return True

    return bool(_has_repeated_long_chunk(t))


@dataclass
class WhisperASRConfig:
    model_dir: str
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "zh"

    beam_size: int = 5
    best_of: int = 5
    temperature: float = 0.0
    vad_filter: bool = False
    condition_on_previous_text: bool = False
    initial_prompt: str = field(default_factory=build_default_initial_prompt)


class FasterWhisperASR:
    def __init__(self, cfg: WhisperASRConfig):
        p = Path(cfg.model_dir).resolve()
        if not p.exists():
            raise FileNotFoundError(f"找不到 whisper 模型目录：{p}")

        self.cfg = cfg
        self.model = WhisperModel(
            str(p), device=cfg.device, compute_type=cfg.compute_type
        )

        self.input_normalizer = InputNormalizer()

        # 多字优先
        self.tc_sc_map = {
            "膝蓋": "膝盖",
            "腳踝": "脚踝",
            "腳趾": "脚趾",
            "右腳": "右脚",
            "左腳": "左脚",
            "沒有": "没有",
            "謝謝": "谢谢",
            "罵": "骂",
            "閉": "闭",
            "腦": "脑",
            "醫": "医",
            "嗎": "吗",
            "沒": "没",
            "會": "会",
            "後": "后",
            "為": "为",
            "裡": "里",
            "這": "这",
            "謝": "谢",
            "腳": "脚",
            "頭": "头",
            "頸": "颈",
        }

    def _to_simplified_light(self, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return t
        for k, v in self.tc_sc_map.items():
            t = t.replace(k, v)
        return t

    def _apply_corrections(self, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return t

        # 1) 繁->简
        t = self._to_simplified_light(t)

        # 2) Shared conservative normalization for ASR/text/benchmark input.
        t = self.input_normalizer.normalize(t).canonical_text

        if is_probable_junk_transcript(t):
            return ""

        return t.strip()

    def transcribe(self, audio) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language=self.cfg.language,
            task="transcribe",
            beam_size=self.cfg.beam_size,
            best_of=self.cfg.best_of,
            temperature=self.cfg.temperature,
            vad_filter=self.cfg.vad_filter,
            condition_on_previous_text=self.cfg.condition_on_previous_text,
            initial_prompt=(self.cfg.initial_prompt or None),
        )
        text = "".join([seg.text for seg in segments]).strip()
        return self._apply_corrections(text)
