"""
monibox/runtime/memory.py

用途
-----
WorkingMemory（工作记忆）：
- 保存最近对话轮次（user/bot）
- 保存 last_user/last_bot，用于重复抑制与润色上下文
- 保存最近若干条 bot 输出，避免“复读机”
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class WorkingMemory:
    max_turns: int = 12
    history: deque[tuple[str, str]] = field(
        default_factory=lambda: deque(maxlen=12)
    )  # (user, bot)
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
        # 如果 last_user 为空也允许（例如某些自动触发）
        self.history.append((self.last_user, t))

    def last_bot_texts(self, n: int = 3) -> list[str]:
        xs = list(self.recent_bot)
        return xs[-n:] if n > 0 else xs

    def is_repeating(self, text: str, threshold: float = 0.92) -> bool:
        """
        粗糙重复检测：与上一句 bot 的字符相似度很高则认为重复。
        """
        a = (self.last_bot or "").strip()
        b = (text or "").strip()
        if not a or not b:
            return False
        if a == b:
            return True

        # 简单相似度：交集/并集（字符级）
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return False
        j = len(sa & sb) / max(1, len(sa | sb))
        return j >= threshold
