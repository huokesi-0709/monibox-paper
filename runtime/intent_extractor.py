from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

INTENT_PRIORITY = [
    "respiratory_distress",
    "severe_bleeding",
    "trapped_or_crush",
    "head_or_consciousness",
    "collapse_aftershock",
    "hypothermia",
    "dehydration",
    "pain_or_injury",
    "panic",
    "low_battery",
    "out_of_scope",
]

INTENT_RISK_SCORE = {
    intent: round(1.0 - idx * 0.09, 2) for idx, intent in enumerate(INTENT_PRIORITY)
}
INTENT_RISK_SCORE["out_of_scope"] = 0.05

HIGH_RISK_INTENTS = {
    "respiratory_distress",
    "severe_bleeding",
    "trapped_or_crush",
    "head_or_consciousness",
    "collapse_aftershock",
}

NEGATION_WORDS = ("没有", "没", "不是", "未", "无", "不")
NEGATION_BOUNDARIES = (
    "但是",
    "不过",
    "然后",
    "还有",
    "并且",
    "而且",
    "同时",
    "另外",
    "还",
    "又",
    "也",
    "，",
    ",",
    "。",
    ".",
    "；",
    ";",
    "、",
    "？",
    "?",
    "！",
    "!",
)
CLAUSE_SPLIT_RE = re.compile(
    r"[，,。.;；、?!？！]+|然后|还有|但是|不过|并且|而且|同时|另外|还|也"
)

BODY_PART_TERMS = (
    "头",
    "脑袋",
    "脖子",
    "胸",
    "胸口",
    "腿",
    "脚",
    "手",
    "胳膊",
    "膝盖",
    "伤口",
)

SCENE_TERMS = (
    "地震",
    "余震",
    "废墟",
    "被困",
    "坍塌",
    "倒塌",
    "压住",
    "埋住",
    "瓦砾",
)

INTENT_TERMS: dict[str, tuple[str, ...]] = {
    "respiratory_distress": (
        "喘不上气",
        "喘不过气",
        "呼吸困难",
        "呼吸很费力",
        "窒息",
        "缺氧",
        "气不够",
        "吸不上气",
        "胸闷喘",
    ),
    "severe_bleeding": (
        "流血",
        "出血",
        "血止不住",
        "一直流血",
        "喷血",
        "冒血",
        "好多血",
        "很多血",
        "伤口流血",
    ),
    "trapped_or_crush": (
        "被困",
        "困住",
        "压住",
        "被压",
        "埋住",
        "卡住",
        "动不了",
        "废墟里",
        "塌下来",
        "困在废墟",
    ),
    "collapse_aftershock": (
        "余震",
        "又震",
        "还在晃",
        "又在晃",
        "地震",
        "坍塌",
        "倒塌",
        "墙在裂",
        "掉东西",
    ),
    "head_or_consciousness": (
        "头晕",
        "意识",
        "昏迷",
        "快晕",
        "要晕",
        "眼前发黑",
        "头部出血",
        "头撞",
        "脑袋疼",
    ),
    "hypothermia": (
        "好冷",
        "很冷",
        "发冷",
        "发抖",
        "失温",
        "冻",
        "体温低",
    ),
    "dehydration": (
        "很渴",
        "好渴",
        "口渴",
        "没水",
        "缺水",
        "嘴干",
        "脱水",
    ),
    "pain_or_injury": (
        "疼",
        "痛",
        "受伤",
        "伤",
        "骨折",
        "断了",
        "扭伤",
        "肿了",
        "麻了",
    ),
    "panic": (
        "害怕",
        "恐慌",
        "慌",
        "怕",
        "紧张",
        "崩溃",
        "想哭",
    ),
    "low_battery": (
        "手机没电",
        "快没电",
        "电量低",
        "没电了",
        "电快没了",
        "快关机",
        "电池快没",
    ),
}

INTENT_TAGS = {
    "respiratory_distress": ("risk_respiratory", "medical_high_risk"),
    "severe_bleeding": ("risk_bleeding", "medical_high_risk"),
    "trapped_or_crush": ("risk_trapped", "scene_crush"),
    "collapse_aftershock": ("risk_aftershock", "scene_earthquake"),
    "head_or_consciousness": ("risk_consciousness", "medical_high_risk"),
    "hypothermia": ("risk_hypothermia",),
    "dehydration": ("risk_dehydration",),
    "pain_or_injury": ("risk_injury",),
    "panic": ("risk_panic",),
    "low_battery": ("risk_low_battery", "device_constraint"),
    "out_of_scope": ("out_of_scope",),
}

NON_NEGATED_INTENTS = {"low_battery"}


@dataclass(frozen=True)
class IntentContext:
    raw_text: str
    clauses: list[str]
    primary_intent: str
    secondary_intents: list[str]
    risk_score: float
    primary_risk_score: float
    tags: list[str]
    body_parts: list[str]
    scene_terms: list[str]
    negated_risks: list[str]
    matched_terms: list[dict[str, Any]]
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        active_intents = [
            self.primary_intent,
            *self.secondary_intents,
        ]
        active_intents = [
            intent for intent in active_intents if intent != "out_of_scope"
        ]
        data.update(
            {
                "num_active_intents": len(active_intents),
                "num_secondary_intents": len(self.secondary_intents),
                "num_negated_risks": len(self.negated_risks),
                "has_high_risk_intent": any(
                    intent in HIGH_RISK_INTENTS for intent in active_intents
                ),
            }
        )
        return data


class IntentExtractor:
    def extract(self, text: str) -> IntentContext:
        raw_text = "" if text is None else str(text)
        normalized = raw_text.strip()
        clauses = self._split_clauses(normalized)
        body_parts = self._collect_terms(normalized, BODY_PART_TERMS)
        scene_terms = self._collect_terms(normalized, SCENE_TERMS)

        active_intents: set[str] = set()
        negated_risks: set[str] = set()
        matched_terms: list[dict[str, Any]] = []
        explanation: list[str] = []

        for intent, terms in INTENT_TERMS.items():
            for term in terms:
                for match in re.finditer(re.escape(term), normalized):
                    clause = self._clause_for_match(clauses, term)
                    negated = (
                        intent not in NON_NEGATED_INTENTS
                        and self._is_negated(normalized, match.start(), match.end())
                    )
                    item = {
                        "intent": intent,
                        "term": term,
                        "clause": clause,
                        "negated": negated,
                        "start": match.start(),
                        "end": match.end(),
                    }
                    matched_terms.append(item)
                    if negated:
                        negated_risks.add(intent)
                        explanation.append(
                            f"{intent} matched '{term}' but was negated near the term"
                        )
                    else:
                        active_intents.add(intent)
                        explanation.append(f"{intent} matched '{term}'")

        primary = self._select_primary(active_intents)
        secondary = [
            intent
            for intent in INTENT_PRIORITY
            if intent in active_intents and intent != primary
        ]

        if primary == "out_of_scope":
            primary_score = INTENT_RISK_SCORE["out_of_scope"]
            risk_score = primary_score
            explanation.append("no in-scope risk terms matched")
        else:
            primary_score = INTENT_RISK_SCORE[primary]
            risk_score = min(1.0, primary_score + max(0, len(secondary)) * 0.03)

        tags = self._build_tags(primary, secondary, body_parts, scene_terms)

        return IntentContext(
            raw_text=raw_text,
            clauses=clauses,
            primary_intent=primary,
            secondary_intents=secondary,
            risk_score=round(risk_score, 3),
            primary_risk_score=round(primary_score, 3),
            tags=tags,
            body_parts=body_parts,
            scene_terms=scene_terms,
            negated_risks=[
                intent for intent in INTENT_PRIORITY if intent in negated_risks
            ],
            matched_terms=matched_terms,
            explanation=explanation,
        )

    @staticmethod
    def _split_clauses(text: str) -> list[str]:
        clauses = [item.strip() for item in CLAUSE_SPLIT_RE.split(text) if item.strip()]
        return clauses or ([text] if text else [])

    @staticmethod
    def _collect_terms(text: str, terms: tuple[str, ...]) -> list[str]:
        return [term for term in terms if term and term in text]

    @staticmethod
    def _clause_for_match(clauses: list[str], term: str) -> str:
        for clause in clauses:
            if term in clause:
                return clause
        return ""

    @staticmethod
    def _is_negated(text: str, start: int, end: int, window: int = 4) -> bool:
        left = text[max(0, start - window) : start]
        right = text[end : min(len(text), end + window)]
        left = IntentExtractor._trim_left_boundary(left)
        right = IntentExtractor._trim_right_boundary(right)
        return any(word in left for word in NEGATION_WORDS) or any(
            word in right for word in NEGATION_WORDS
        )

    @staticmethod
    def _trim_left_boundary(text: str) -> str:
        cut = -1
        for boundary in NEGATION_BOUNDARIES:
            idx = text.rfind(boundary)
            if idx > cut:
                cut = idx + len(boundary)
        return text[cut:] if cut >= 0 else text

    @staticmethod
    def _trim_right_boundary(text: str) -> str:
        cut = len(text)
        for boundary in NEGATION_BOUNDARIES:
            idx = text.find(boundary)
            if idx >= 0 and idx < cut:
                cut = idx
        return text[:cut]

    @staticmethod
    def _select_primary(active_intents: set[str]) -> str:
        for intent in INTENT_PRIORITY:
            if intent in active_intents:
                return intent
        return "out_of_scope"

    @staticmethod
    def _build_tags(
        primary: str,
        secondary: list[str],
        body_parts: list[str],
        scene_terms: list[str],
    ) -> list[str]:
        tags: list[str] = []
        for intent in [primary, *secondary]:
            for tag in INTENT_TAGS.get(intent, ()):
                if tag not in tags:
                    tags.append(tag)
        for part in body_parts:
            tag = f"body:{part}"
            if tag not in tags:
                tags.append(tag)
        for scene in scene_terms:
            tag = f"scene:{scene}"
            if tag not in tags:
                tags.append(tag)
        return tags
