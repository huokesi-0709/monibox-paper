from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from runtime.intent_extractor import NEGATION_BOUNDARIES, NEGATION_WORDS


TRAPPED_AFFIRMING_RIGHT_CONTEXTS = (
    "出不去",
    "出不来",
    "出不来了",
    "走不了",
    "打不开",
    "门打不开",
)


@dataclass(frozen=True)
class NegationConfig:
    negation_window: int = 6
    negation_words: tuple[str, ...] = NEGATION_WORDS
    boundary_terms: tuple[str, ...] = NEGATION_BOUNDARIES
    negation_penalty: float = 0.45
    non_negatable_risks: tuple[str, ...] = ("low_battery", "out_of_scope")


@dataclass(frozen=True)
class NegationResult:
    positive_risks: list[str]
    negated_risks: list[str]
    mentions: list[dict[str, Any]]
    negation_trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NegationResolver:
    def __init__(self, config: NegationConfig | None = None) -> None:
        self.config = config or NegationConfig()

    def resolve(
        self, text: str, risk_mentions: list[dict[str, Any]]
    ) -> NegationResult:
        normalized = "" if text is None else str(text)
        positive_risks: list[str] = []
        negated_risks: list[str] = []
        resolved_mentions: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []

        for mention in risk_mentions:
            risk = str(mention.get("risk") or "")
            start = int(mention.get("start") or 0)
            end = int(mention.get("end") or start)
            negated = (
                risk not in set(self.config.non_negatable_risks)
                and self._is_negated(normalized, start, end)
            )
            adjusted = dict(mention)
            adjusted["negated"] = negated
            if negated:
                adjusted["confidence"] = round(
                    float(adjusted.get("confidence") or 0.0)
                    * (1.0 - self.config.negation_penalty),
                    4,
                )
                append_unique(negated_risks, risk)
            else:
                append_unique(positive_risks, risk)
            resolved_mentions.append(adjusted)
            trace.append(
                {
                    "risk": risk,
                    "term": adjusted.get("term", ""),
                    "start": start,
                    "end": end,
                    "negated": negated,
                    "left_window": self._left_window(normalized, start),
                    "right_window": self._right_window(normalized, end),
                }
            )

        return NegationResult(
            positive_risks=positive_risks,
            negated_risks=negated_risks,
            mentions=resolved_mentions,
            negation_trace=trace,
        )

    def _is_negated(self, text: str, start: int, end: int) -> bool:
        left = self._left_window(text, start)
        right = self._right_window(text, end)
        if any(phrase in right for phrase in TRAPPED_AFFIRMING_RIGHT_CONTEXTS):
            return False
        return any(word in left for word in self.config.negation_words) or any(
            word in right for word in self.config.negation_words
        )

    def _left_window(self, text: str, start: int) -> str:
        window = text[max(0, start - self.config.negation_window) : start]
        return self._trim_left_boundary(window)

    def _right_window(self, text: str, end: int) -> str:
        window = text[end : min(len(text), end + self.config.negation_window)]
        return self._trim_right_boundary(window)

    def _trim_left_boundary(self, text: str) -> str:
        cut = -1
        for boundary in self.config.boundary_terms:
            idx = text.rfind(boundary)
            if idx > cut:
                cut = idx + len(boundary)
        return text[cut:] if cut >= 0 else text

    def _trim_right_boundary(self, text: str) -> str:
        cut = len(text)
        for boundary in self.config.boundary_terms:
            idx = text.find(boundary)
            if 0 <= idx < cut:
                cut = idx
        return text[:cut]


def append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
