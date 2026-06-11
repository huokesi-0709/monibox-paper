"""
monibox/runtime/repeat_guard.py

用途
-----
RepeatGuard：重复抑制（同一句不连播）
- 基于 WorkingMemory.last_bot / recent_bot 做检测
- 返回：是否重复 + 建议动作（改用变体/缩短/改问句）

原则
----
- 不做复杂 NLP，采用可控启发式（离线、稳定）
"""

from __future__ import annotations

from dataclasses import dataclass


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

        # 与最近1~2句比较
        scores = []
        for prev in recent_bot[-2:]:
            scores.append(_jaccard_char(cand, prev))

        score = max(scores) if scores else 0.0
        if score < self.threshold:
            return RepeatDecision(False, score, "none")

        # 重复：优先尝试变体；如果还是重复，建议缩短或转为跟进问句
        if len(cand) > 25:
            return RepeatDecision(True, score, "variant", note="long_repeat")
        return RepeatDecision(True, score, "followup", note="short_repeat")
