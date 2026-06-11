"""
Runtime support utilities: working memory, repeat guard, variants, hardware iface.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# ---------- memory ----------


@dataclass
class WorkingMemory:
    max_turns: int = 12
    history: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=12))
    last_user: str = ""
    last_bot: str = ""
    recent_bot: deque[str] = field(default_factory=lambda: deque(maxlen=6))

    def push_user(self, text: str):
        self.last_user = (text or "").strip()

    def push_bot(self, text: str):
        t = (text or "").strip()
        self.last_bot = t
        if t:
            self.recent_bot.append(t)
        self.history.append((self.last_user, t))

    def last_bot_texts(self, n: int = 3) -> list[str]:
        xs = list(self.recent_bot)
        return xs[-n:] if n > 0 else xs

    def is_repeating(self, text: str, threshold: float = 0.92) -> bool:
        a = (self.last_bot or "").strip()
        b = (text or "").strip()
        if not a or not b:
            return False
        if a == b:
            return True
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return False
        j = len(sa & sb) / max(1, len(sa | sb))
        return j >= threshold


# ---------- repeat_guard ----------


def _jaccard_char(a: str, b: str) -> float:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(1, len(sa | sb))


@dataclass
class RepeatDecision:
    is_repeat: bool
    score: float
    mode: str  # "none" / "variant" / "shorten" / "followup"
    note: str = ""


class RepeatGuard:
    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold

    def decide(self, candidate: str, recent_bot: list[str]) -> RepeatDecision:
        cand = (candidate or "").strip()
        if not cand:
            return RepeatDecision(False, 0.0, "none")

        scores = []
        for prev in recent_bot[-2:]:
            scores.append(_jaccard_char(cand, prev))

        score = max(scores) if scores else 0.0
        if score < self.threshold:
            return RepeatDecision(False, score, "none")

        if len(cand) > 25:
            return RepeatDecision(True, score, "variant", note="long_repeat")
        return RepeatDecision(True, score, "followup", note="short_repeat")


# ---------- variants ----------


@dataclass
class VariantBank:
    variants: dict[str, list[str]] = field(default_factory=dict)
    rr_index: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, items: list[str]):
        xs = [x.strip() for x in (items or []) if x and x.strip()]
        if not xs:
            return
        self.variants.setdefault(key, [])
        for x in xs:
            if x not in self.variants[key]:
                self.variants[key].append(x)

    def pick(self, key: str, default: str = "", mode: str = "rr") -> str:
        xs = self.variants.get(key) or []
        if not xs:
            return default
        if mode == "rand":
            return random.choice(xs)
        i = self.rr_index.get(key, 0) % len(xs)
        self.rr_index[key] = i + 1
        return xs[i]


def build_default_variant_bank() -> VariantBank:
    vb = VariantBank()

    vb.add(
        "generic:reask",
        ["我没听清。", "刚才那句我没听明白。", "再说一遍也可以，我在听。"],
    )
    vb.add(
        "protocol:prot_noise_ignore:main",
        [
            "我听到了。先说哪里不舒服。",
            "我听到了。你有出血、疼痛或喘不过气吗？",
            "我在听。先说最难受的地方。",
        ],
    )
    vb.add(
        "protocol:prot_bleeding_control:main",
        ["先压住伤口别松手。", "先用布压住伤口，别松手。", "先稳住，用衣物压住伤口。"],
    )
    vb.add(
        "protocol:prot_bleeding_control:qa_location_ack",
        ["好，是你的{location}。", "明白，在{location}。", "收到，{location}在流血。"],
    )
    vb.add(
        "protocol:prot_bleeding_control:qa_yesno_ack_yes", ["好。", "明白。", "收到。"]
    )
    vb.add(
        "protocol:prot_bleeding_control:qa_yesno_ack_no", ["明白。", "好。", "收到。"]
    )
    vb.add(
        "protocol:prot_injury_fracture:main",
        ["先别动受伤部位。", "先停下来，别移动伤处。", "先别挣扎，保持不动。"],
    )
    vb.add(
        "protocol:prot_panic_breathing:main",
        ["先跟我数拍呼吸。", "先把呼吸稳住，跟我一起数。", "别急，先按节奏呼吸。"],
    )
    vb.add(
        "low:generic:main",
        [
            "你哪里最不舒服？出血的话先告诉我。",
            "你最难受的是哪里？疼痛、出血还是喘不过气？",
            "你先说最急的情况。身上有伤的话先说。",
        ],
    )

    return vb


# ---------- hardware_iface ----------


class HardwareIface:
    def tts(self, text: str, style: str | None = None): ...
    def led(self, pattern: dict[str, Any]): ...
    def screen(self, text: str, ms: int = 2000): ...


class MockHardware(HardwareIface):
    def tts(self, text: str, style: str | None = None):
        print(f"[TTS style={style}] {text}")

    def led(self, pattern: dict[str, Any]):
        print(f"[LED] {pattern}")

    def screen(self, text: str, ms: int = 2000):
        print(f"[SCREEN {ms}ms] {text}")
