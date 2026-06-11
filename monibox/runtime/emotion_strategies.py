from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from monibox.config import KNOWLEDGE_SRC

EMOTION_STRATEGIES_PATH = KNOWLEDGE_SRC / "emotion_strategies.json"
BUCKET_DEFAULT_EMOTIONS = {
    "cold": "weak",
    "thirst": "weak",
    "hunger": "weak",
    "fatigue": "weak",
    "panic": "panic",
    "pain": "pain",
    "vision": "confused",
    "rescue": "stable",
    "generic": "stable",
}
REQUIRED_EMOTIONS = (
    "panic",
    "pain",
    "weak",
    "confused",
    "despair",
    "angry",
    "numb",
    "stable",
)


@dataclass(frozen=True)
class EmotionStrategy:
    emotion: str
    keywords: tuple[str, ...]
    negative_keywords: tuple[str, ...]
    style: str
    tts_style: str
    led_pattern: dict
    screen_text: str
    max_sentences: int
    max_chars: int
    response_shape: str
    llm_rewrite_allowed: bool
    priority_boost: int
    handoff_protocols: tuple[str, ...]


def _read_raw(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("emotion_strategies.json 根节点必须是对象")
    return data


def load_emotion_strategies(path: str | Path | None = None) -> list[EmotionStrategy]:
    target = Path(path) if path else EMOTION_STRATEGIES_PATH
    raw = _read_raw(target)
    items = raw.get("strategies")
    if not isinstance(items, list):
        raise ValueError("emotion_strategies.json 缺少 strategies 数组")

    strategies: list[EmotionStrategy] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("emotion strategy 条目必须是对象")
        strategies.append(
            EmotionStrategy(
                emotion=str(item.get("emotion") or "").strip(),
                keywords=tuple(
                    str(x).strip() for x in item.get("keywords") or [] if str(x).strip()
                ),
                negative_keywords=tuple(
                    str(x).strip()
                    for x in item.get("negative_keywords") or []
                    if str(x).strip()
                ),
                style=str(item.get("style") or "").strip(),
                tts_style=str(item.get("tts_style") or "").strip(),
                led_pattern=dict(item.get("led_pattern") or {}),
                screen_text=str(item.get("screen_text") or "").strip(),
                max_sentences=int(item.get("max_sentences") or 0),
                max_chars=int(item.get("max_chars") or 0),
                response_shape=str(item.get("response_shape") or "").strip(),
                llm_rewrite_allowed=bool(item.get("llm_rewrite_allowed")),
                priority_boost=int(item.get("priority_boost") or 0),
                handoff_protocols=tuple(
                    str(x).strip()
                    for x in item.get("handoff_protocols") or []
                    if str(x).strip()
                ),
            )
        )
    return strategies


class EmotionStrategyBook:
    def __init__(self, strategies: Iterable[EmotionStrategy] | None = None):
        loaded = (
            list(strategies) if strategies is not None else load_emotion_strategies()
        )
        self._strategies = loaded
        self._by_emotion = {item.emotion: item for item in loaded}

    @property
    def strategies(self) -> list[EmotionStrategy]:
        return list(self._strategies)

    def get(self, emotion: str) -> EmotionStrategy:
        item = self._by_emotion.get(str(emotion or "").strip())
        if item is None:
            raise KeyError(f"unknown emotion strategy: {emotion}")
        return item

    def fallback_for_bucket(self, bucket: str) -> EmotionStrategy:
        emotion = BUCKET_DEFAULT_EMOTIONS.get(str(bucket or "").strip(), "stable")
        return self.get(emotion)

    def detect(
        self,
        text: str,
        *,
        allowed: Iterable[str] | None = None,
        fallback_stable: bool = False,
    ) -> EmotionStrategy | None:
        source = (text or "").strip()
        if not source:
            return self.get("stable") if fallback_stable else None

        allowed_set = {str(x).strip() for x in allowed} if allowed is not None else None
        for item in self._strategies:
            if item.emotion == "stable":
                continue
            if allowed_set is not None and item.emotion not in allowed_set:
                continue
            if any(token in source for token in item.negative_keywords):
                continue
            if any(token in source for token in item.keywords):
                return item

        if (
            allowed_set is not None
            and "stable" not in allowed_set
            and not fallback_stable
        ):
            return None
        return self.get("stable") if fallback_stable else None


def load_emotion_strategy_book(path: str | Path | None = None) -> EmotionStrategyBook:
    if path is None:
        return EmotionStrategyBook()
    return EmotionStrategyBook(load_emotion_strategies(path))
