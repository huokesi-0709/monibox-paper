from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import PROJECT_ROOT


@dataclass(frozen=True)
class Correction:
    source: str
    target: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedInput:
    raw_text: str
    canonical_text: str
    corrections: list[Correction]
    noise_removed: list[str]
    repeated_terms_collapsed: list[str]

    def trace_dict(self) -> dict[str, object]:
        normalized_raw = InputNormalizer.normalize_form(self.raw_text)
        return {
            "raw_text": self.raw_text,
            "canonical_text": self.canonical_text,
            "corrections": [item.to_dict() for item in self.corrections],
            "noise_removed": list(self.noise_removed),
            "repeated_terms_collapsed": list(self.repeated_terms_collapsed),
            "changed": (
                self.canonical_text != normalized_raw
                or bool(self.corrections)
                or bool(self.noise_removed)
                or bool(self.repeated_terms_collapsed)
            ),
            "num_corrections": len(self.corrections),
            "num_noise_removed": len(self.noise_removed),
            "num_repeated_terms_collapsed": len(self.repeated_terms_collapsed),
        }


@dataclass(frozen=True)
class FuzzyCorrectionRule:
    context_keywords: tuple[str, ...]
    pattern: str
    replacement: str


BUILTIN_CORRECTIONS: tuple[Correction, ...] = (
    Correction("退在留血", "腿在流血", "builtin_asr_exact"),
    Correction("退在流血", "腿在流血", "builtin_asr_exact"),
    Correction("留血", "流血", "builtin_asr_exact"),
    Correction("穿不上气", "喘不上气", "builtin_asr_exact"),
    Correction("穿不过气", "喘不过气", "builtin_asr_exact"),
    Correction("旧我", "救我", "builtin_asr_exact"),
    Correction("地真", "地震", "builtin_asr_exact"),
)

PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "；": ";",
        "：": ":",
        "、": ",",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "—": "-",
        "～": "~",
    }
)

NOISE_TOKENS = (
    "呃",
    "嗯",
    "啊",
    "额",
    "那个",
    "这个",
    "就是",
    "然后",
    "你知道",
)


def _load_asr_corrections(path: Path) -> list[Correction]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    raw_corrections = data.get("corrections", {})
    if not isinstance(raw_corrections, dict):
        return []

    corrections: list[Correction] = []
    for source, target in raw_corrections.items():
        if isinstance(source, str) and isinstance(target, str) and source and target:
            corrections.append(Correction(source, target, "knowledge_asr_exact"))
    corrections.sort(key=lambda item: len(item.source), reverse=True)
    return corrections


def _load_fuzzy_correction_rules(path: Path) -> list[FuzzyCorrectionRule]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    fuzzy_patterns = data.get("fuzzy_patterns", {})
    if not isinstance(fuzzy_patterns, dict):
        return []

    raw_rules = fuzzy_patterns.get("rules", [])
    if not isinstance(raw_rules, list):
        return []

    rules: list[FuzzyCorrectionRule] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            continue
        context_keywords = raw_rule.get("context_keywords", [])
        pattern = raw_rule.get("pattern")
        replacement = raw_rule.get("replacement")
        if (
            not isinstance(context_keywords, list)
            or not all(isinstance(item, str) and item for item in context_keywords)
            or not isinstance(pattern, str)
            or not pattern
            or not isinstance(replacement, str)
            or not replacement
        ):
            continue
        try:
            re.compile(pattern)
        except re.error:
            continue
        rules.append(
            FuzzyCorrectionRule(
                context_keywords=tuple(context_keywords),
                pattern=pattern,
                replacement=replacement,
            )
        )
    return rules


class InputNormalizer:
    def __init__(self, corrections_path: str | Path | None = None):
        path = (
            PROJECT_ROOT / "knowledge" / "asr_corrections.json"
            if corrections_path is None
            else Path(corrections_path)
        )
        self._corrections = [*BUILTIN_CORRECTIONS, *_load_asr_corrections(path)]
        self._corrections.sort(key=lambda item: len(item.source), reverse=True)
        self._fuzzy_rules = _load_fuzzy_correction_rules(path)

    def normalize(self, raw_text: str) -> NormalizedInput:
        raw = "" if raw_text is None else str(raw_text)
        text = self.normalize_form(raw)
        corrections: list[Correction] = []
        noise_removed: list[str] = []
        repeated_terms_collapsed: list[str] = []

        if not text:
            return NormalizedInput(raw, "", [], [], [])

        text, removed = self._remove_oral_noise(text)
        noise_removed.extend(removed)

        for correction in self._corrections:
            if correction.source in text:
                text = text.replace(correction.source, correction.target)
                corrections.append(correction)

        text, phrase_corrections = self._normalize_rescue_phrase(text)
        corrections.extend(phrase_corrections)

        text, fuzzy_corrections = self._apply_fuzzy_context_corrections(text)
        corrections.extend(fuzzy_corrections)

        text, collapsed = self._collapse_repeated_terms(text)
        repeated_terms_collapsed.extend(collapsed)
        text = self._final_cleanup(text)

        return NormalizedInput(
            raw_text=raw,
            canonical_text=text,
            corrections=corrections,
            noise_removed=noise_removed,
            repeated_terms_collapsed=repeated_terms_collapsed,
        )

    @staticmethod
    def normalize_form(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text or "")
        normalized = normalized.replace("\u3000", " ")
        normalized = normalized.translate(PUNCTUATION_TRANSLATION)
        return re.sub(r"\s+", " ", normalized).strip()

    _normalize_form = normalize_form

    @staticmethod
    def _remove_oral_noise(text: str) -> tuple[str, list[str]]:
        removed: list[str] = []
        result = text
        for token in NOISE_TOKENS:
            pattern = rf"(?:(?<=^)|(?<=[\s,.;:!?])){re.escape(token)}(?=$|[\s,.;:!?])"
            if re.search(pattern, result):
                removed.append(token)
                result = re.sub(pattern, " ", result)
        if removed:
            result = re.sub(r"\s*([,.;:!?])(?:\s*[,.;:!?])+", r"\1", result)
            result = re.sub(r"^[\s,.;:!?]+|[\s,.;:!?]+$", "", result)
        result = re.sub(r"\s+", " ", result).strip()
        return result, removed

    @staticmethod
    def _collapse_repeated_terms(text: str) -> tuple[str, list[str]]:
        collapsed: list[str] = []
        result = text

        for size in range(4, 0, -1):
            pattern = re.compile(rf"([\u4e00-\u9fff]{{{size}}})(?:\1){{2,}}")

            def repl(match: re.Match[str]) -> str:
                term = match.group(1)
                collapsed.append(term)
                return term

            result = pattern.sub(repl, result)

        return result, collapsed

    @staticmethod
    def _normalize_rescue_phrase(text: str) -> tuple[str, list[Correction]]:
        corrections: list[Correction] = []
        pattern = re.compile(r"([腿手脚胳膊头脑袋伤口])[,，、\s]*(?:留|流)?[,，、\s]*血")

        def repl(match: re.Match[str]) -> str:
            source = match.group(0)
            target = f"{match.group(1)}在流血"
            if source != target:
                corrections.append(Correction(source, target, "rescue_phrase_normalize"))
            return target

        return pattern.sub(repl, text), corrections

    def _apply_fuzzy_context_corrections(
        self, text: str
    ) -> tuple[str, list[Correction]]:
        corrections: list[Correction] = []
        result = text

        for rule in self._fuzzy_rules:
            if not any(keyword in result for keyword in rule.context_keywords):
                continue

            replacement = rule.replacement

            def repl(
                match: re.Match[str], replacement: str = replacement
            ) -> str:
                source = match.group(0)
                target = match.expand(replacement)
                if source != target:
                    corrections.append(
                        Correction(source, target, "knowledge_asr_fuzzy_context")
                    )
                return target

            result = re.sub(rule.pattern, repl, result)

        return result, corrections

    @staticmethod
    def _final_cleanup(text: str) -> str:
        result = re.sub(r"\s+", " ", text).strip()
        result = re.sub(r"\s*([,.;:!?])\s*", r"\1", result)
        return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", result)
