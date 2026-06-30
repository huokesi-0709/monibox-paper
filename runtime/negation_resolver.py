from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import exp
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

COUNTERFACTUAL_TRIGGERS = ("如果", "假如", "万一", "要是")


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


@dataclass(frozen=True)
class NegationDecision:
    negated: bool
    negation_reason: str
    left_window: str
    right_window: str
    boundary_blocked: bool = False
    counterfactual: bool = False
    negation_probability: float = 0.0
    negation_strength: float = 0.0
    distance_decay: float = 0.0
    boundary_penalty: float = 0.0


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
            start, end = mention_bounds(mention)
            decision = self._classify_negation(normalized, start, end)
            negated = (
                risk not in set(self.config.non_negatable_risks)
                and decision.negated
            )
            negation_reason = decision.negation_reason if negated else ""
            adjusted = dict(mention)
            adjusted["negated"] = negated
            adjusted["negation_reason"] = negation_reason
            adjusted["left_window"] = decision.left_window
            adjusted["right_window"] = decision.right_window
            adjusted["boundary_blocked"] = decision.boundary_blocked
            adjusted["counterfactual"] = decision.counterfactual
            adjusted["negation_probability"] = round(
                decision.negation_probability, 4
            )
            adjusted["negation_strength"] = round(decision.negation_strength, 4)
            adjusted["distance_decay"] = round(decision.distance_decay, 4)
            adjusted["boundary_penalty"] = round(decision.boundary_penalty, 4)
            base_confidence = float(adjusted.get("confidence") or 0.0)
            if negated:
                adjusted["adjusted_confidence"] = round(
                    base_confidence * (1.0 - self.config.negation_penalty), 4
                )
                append_unique(negated_risks, risk)
            else:
                adjusted["adjusted_confidence"] = round(base_confidence, 4)
                append_unique(positive_risks, risk)
            resolved_mentions.append(adjusted)
            trace.append(
                {
                    "risk": risk,
                    "term": adjusted.get("term", adjusted.get("trigger", "")),
                    "trigger": adjusted.get("trigger", adjusted.get("term", "")),
                    "start": start,
                    "end": end,
                    "negated": negated,
                    "negation_reason": negation_reason,
                    "confidence": base_confidence,
                    "adjusted_confidence": adjusted["adjusted_confidence"],
                    "left_window": decision.left_window,
                    "right_window": decision.right_window,
                    "boundary_blocked": decision.boundary_blocked,
                    "counterfactual": decision.counterfactual,
                    "negation_probability": round(decision.negation_probability, 4),
                    "negation_strength": round(decision.negation_strength, 4),
                    "distance_decay": round(decision.distance_decay, 4),
                    "boundary_penalty": round(decision.boundary_penalty, 4),
                }
            )

        return NegationResult(
            positive_risks=positive_risks,
            negated_risks=negated_risks,
            mentions=resolved_mentions,
            negation_trace=trace,
        )

    def _is_negated(self, text: str, start: int, end: int) -> bool:
        return self._classify_negation(text, start, end).negated

    def _classify_negation(self, text: str, start: int, end: int) -> NegationDecision:
        raw_left = self._raw_left_window(text, start)
        raw_right = self._raw_right_window(text, end)
        left = self._left_window(text, start)
        right = self._right_window(text, end)
        boundary_blocked = (
            self._has_negation_word(raw_left) and not self._has_negation_word(left)
        ) or (
            self._has_negation_word(raw_right) and not self._has_negation_word(right)
        )
        counterfactual = self._has_counterfactual(raw_left) or self._has_counterfactual(
            raw_right
        )
        negation_strength = self._negation_strength(left, right)
        distance_decay = self._distance_decay(left, right)
        boundary_penalty = 0.5 if boundary_blocked else 0.0
        negation_probability = self._negation_probability(
            negation_strength, distance_decay, boundary_penalty
        )
        if any(phrase in right for phrase in TRAPPED_AFFIRMING_RIGHT_CONTEXTS):
            return NegationDecision(
                negated=False,
                negation_reason="",
                left_window=left,
                right_window=right,
                boundary_blocked=boundary_blocked,
                counterfactual=counterfactual,
                negation_probability=negation_probability,
                negation_strength=negation_strength,
                distance_decay=distance_decay,
                boundary_penalty=boundary_penalty,
            )
        if self._has_negation_word(left):
            return NegationDecision(
                negated=True,
                negation_reason="negation_word_in_left_window",
                left_window=left,
                right_window=right,
                boundary_blocked=boundary_blocked,
                counterfactual=counterfactual,
                negation_probability=negation_probability,
                negation_strength=negation_strength,
                distance_decay=distance_decay,
                boundary_penalty=boundary_penalty,
            )
        if self._has_negation_word(right):
            return NegationDecision(
                negated=True,
                negation_reason="negation_word_in_right_window",
                left_window=left,
                right_window=right,
                boundary_blocked=boundary_blocked,
                counterfactual=counterfactual,
                negation_probability=negation_probability,
                negation_strength=negation_strength,
                distance_decay=distance_decay,
                boundary_penalty=boundary_penalty,
            )
        return NegationDecision(
            negated=False,
            negation_reason="",
            left_window=left,
            right_window=right,
            boundary_blocked=boundary_blocked,
            counterfactual=counterfactual,
            negation_probability=negation_probability,
            negation_strength=negation_strength,
            distance_decay=distance_decay,
            boundary_penalty=boundary_penalty,
        )

    def _raw_left_window(self, text: str, start: int) -> str:
        return text[max(0, start - self.config.negation_window) : start]

    def _raw_right_window(self, text: str, end: int) -> str:
        return text[end : min(len(text), end + self.config.negation_window)]

    def _left_window(self, text: str, start: int) -> str:
        return self._trim_left_boundary(self._raw_left_window(text, start))

    def _right_window(self, text: str, end: int) -> str:
        return self._trim_right_boundary(self._raw_right_window(text, end))

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

    def _has_negation_word(self, text: str) -> bool:
        return any(word in text for word in self.config.negation_words)

    def _has_counterfactual(self, text: str) -> bool:
        return any(trigger in text for trigger in COUNTERFACTUAL_TRIGGERS)

    def _negation_strength(self, left: str, right: str) -> float:
        return 1.0 if (self._has_negation_word(left) or self._has_negation_word(right)) else 0.0

    def _distance_decay(self, left: str, right: str) -> float:
        distance = min(len(left), len(right))
        return round(exp(-distance / max(1, self.config.negation_window)), 4)

    def _negation_probability(
        self, negation_strength: float, distance_decay: float, boundary_penalty: float
    ) -> float:
        raw = 0.15 + 1.8 * negation_strength + 0.9 * distance_decay - 1.4 * boundary_penalty
        return 1.0 / (1.0 + exp(-raw))


def append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def mention_bounds(mention: dict[str, Any]) -> tuple[int, int]:
    if "start" in mention or "end" in mention:
        start = int(mention.get("start") or 0)
        return start, int(mention.get("end") or start)
    span = mention.get("span")
    if isinstance(span, list) and len(span) == 2:
        start = int(span[0] or 0)
        return start, int(span[1] or start)
    return 0, 0
