from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from runtime.intent_extractor import (
    INTENT_PRIORITY,
    INTENT_TAGS,
    INTENT_TERMS,
    IntentContext,
    IntentExtractor,
)


@dataclass(frozen=True)
class ProtocolMatchResult:
    matched: bool
    protocol_id: str | None
    protocol_name: str | None
    confidence: float
    priority: int
    matched_terms: list[str]
    body_part_matches: list[str]
    scene_matches: list[str]
    negation_conflict: bool
    reason: list[str]
    protocol: dict[str, Any] | None
    score_breakdown: dict[str, float] = field(default_factory=dict)
    threshold: float = 0.0
    active_risks: list[str] = field(default_factory=list)
    negated_risks: list[str] = field(default_factory=list)
    protocol_risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["protocol"] = self.protocol
        return data


class ProtocolEngine:
    """
    协议引擎：
    - 兼容 protocols.json 顶层 list 或 dict({"protocols":[...]})
    - priority 降序匹配
    - 保留旧 match() 的 dict/None 返回，同时新增可解释置信度接口
    """

    MATCH_THRESHOLD = 0.5

    def __init__(self, protocols_path: str | None = None):
        if protocols_path is None:
            protocols_path = str(PROJECT_ROOT / "knowledge" / "protocols.json")

        self.protocols_path = Path(protocols_path)
        self.protocols: list[dict[str, Any]] = []
        self._load_protocols()

    def _load_protocols(self):
        if not self.protocols_path.exists():
            self.protocols = []
            return

        data = json.loads(self.protocols_path.read_text(encoding="utf-8"))

        if isinstance(data, list):
            protos = data
        elif isinstance(data, dict):
            if "protocols" in data and isinstance(data["protocols"], list):
                protos = data["protocols"]
            else:
                raise ValueError(
                    "protocols.json top-level dict must contain key='protocols'. "
                    f"keys={list(data.keys())}"
                )
        else:
            raise ValueError(
                f"protocols.json top-level must be list or dict, got {type(data)}"
            )

        protos = [p for p in protos if isinstance(p, dict)]
        protos = sorted(
            protos, key=lambda p: int(p.get("priority", 0) or 0), reverse=True
        )

        seen = {}
        deduped: list[dict[str, Any]] = []
        dup_list: list[str] = []

        for p in protos:
            pid = str(p.get("protocol_id") or "").strip()
            if not pid:
                deduped.append(p)
                continue
            if pid in seen:
                dup_list.append(pid)
                continue
            seen[pid] = True
            deduped.append(p)

        if dup_list:
            uniq = sorted(set(dup_list))
            print(
                f"[ProtocolEngine] WARNING: duplicated protocol_id detected and deduped: {uniq}"
            )

        self.protocols = deduped

    def match(
        self,
        text: str,
        routed_tags: list[str] | None = None,
        events: list[str] | None = None,
    ) -> dict[str, Any] | None:
        # Legacy compatibility only. Paper evaluation and the main MoniSession
        # path should use match_with_score(), which returns confidence and
        # traceable reasons instead of a trigger-only dict/None result.
        text = text or ""
        routed_tags = routed_tags or []
        events = events or []

        result = self.match_with_score(
            text,
            routed_tags,
            events,
            intent_context=IntentExtractor().extract(text),
        )
        if result.matched:
            return result.protocol
        if result.negation_conflict:
            return None

        # Compatibility fallback: old callers expect pure trigger hit behavior.
        for p in self.protocols:
            trig = p.get("trigger", {}) or {}
            if self._eval_trigger(trig, text, routed_tags, events):
                return p
        return None

    def match_with_score(
        self,
        text: str,
        routed_tags: list[str] | None = None,
        events: list[str] | None = None,
        intent_context: IntentContext | dict[str, Any] | None = None,
    ) -> ProtocolMatchResult:
        text = text or ""
        routed_tags = routed_tags or []
        events = events or []
        ctx = self._intent_context_dict(intent_context)

        best: ProtocolMatchResult | None = None
        for protocol in self.protocols:
            result = self._score_protocol(protocol, text, routed_tags, events, ctx)
            if best is None or (result.confidence, result.priority) > (
                best.confidence,
                best.priority,
            ):
                best = result

        if best is None:
            return ProtocolMatchResult(
                matched=False,
                protocol_id=None,
                protocol_name=None,
                confidence=0.0,
                priority=0,
                matched_terms=[],
                body_part_matches=[],
                scene_matches=[],
                negation_conflict=False,
                reason=["no protocols loaded"],
                protocol=None,
                threshold=self.MATCH_THRESHOLD,
            )
        return best

    def _score_protocol(
        self,
        protocol: dict[str, Any],
        text: str,
        routed_tags: list[str],
        events: list[str],
        ctx: dict[str, Any],
    ) -> ProtocolMatchResult:
        trigger = protocol.get("trigger", {}) or {}
        priority = int(protocol.get("priority", 0) or 0)
        priority_norm = max(0.0, min(1.0, priority / 100.0))

        protocol_terms = self._extract_text_terms(protocol)
        matched_terms = [term for term in protocol_terms if term and term in text]
        matched_terms = self._dedupe(matched_terms)

        event_hit = self._has_event_match(trigger, events)
        keyword_hit = 1.0 if matched_terms or event_hit else 0.0

        body_parts = [str(x) for x in ctx.get("body_parts", []) if str(x)]
        scene_terms = [str(x) for x in ctx.get("scene_terms", []) if str(x)]
        body_part_matches = [part for part in body_parts if part in text]
        scene_matches = [
            scene
            for scene in scene_terms
            if scene in text and (scene in matched_terms or self._protocol_mentions(protocol, scene))
        ]

        protocol_risks = self._infer_protocol_risks(protocol, matched_terms)
        active_risks = {
            str(ctx.get("primary_intent") or ""),
            *[str(x) for x in ctx.get("secondary_intents", [])],
        }
        active_risks.discard("")
        active_risks.discard("out_of_scope")
        negated_risks = {str(x) for x in ctx.get("negated_risks", [])}
        negated_risks.discard("")
        risk_term_hit = 1.0 if protocol_risks & active_risks else 0.0
        negation_conflict = bool(protocol_risks & negated_risks)

        routed_tag_match = (
            1.0
            if self._has_tag_match(trigger, routed_tags, ctx)
            or self._has_protocol_risk_tag_match(protocol_risks, routed_tags, ctx)
            else 0.0
        )
        body_part_match = 1.0 if body_part_matches and protocol_risks else 0.0
        scene_match = 1.0 if scene_matches else 0.0

        none_conflict = self._none_of_conflict(trigger, text, routed_tags, events)
        if none_conflict:
            negation_conflict = True

        confidence = (
            0.35 * keyword_hit
            + 0.25 * float(event_hit)
            + 0.20 * risk_term_hit
            + 0.15 * body_part_match
            + 0.15 * scene_match
            + 0.10 * routed_tag_match
            + 0.05 * priority_norm
            - 0.30 * float(negation_conflict)
        )
        confidence = max(0.0, min(1.0, confidence))

        reason = []
        if matched_terms:
            reason.append(f"keyword terms matched: {matched_terms}")
        if event_hit:
            reason.append("event trigger matched")
        if protocol_risks:
            reason.append(f"protocol risks inferred: {sorted(protocol_risks)}")
        if risk_term_hit:
            reason.append(f"intent risks matched: {sorted(protocol_risks & active_risks)}")
        if body_part_matches:
            reason.append(f"body parts matched: {body_part_matches}")
        if scene_matches:
            reason.append(f"scene terms matched: {scene_matches}")
        if routed_tag_match:
            reason.append("routed tags / intent tags matched")
        if negation_conflict:
            reason.append(f"negation conflict: {sorted(protocol_risks & negated_risks)}")
        if none_conflict:
            reason.append("protocol none_of/exclude_words conflict")
        if not reason:
            reason.append("no explanatory evidence matched")

        score_breakdown = {
            "keyword_hit": keyword_hit,
            "event_hit": float(event_hit),
            "risk_term_hit": risk_term_hit,
            "body_part_match": body_part_match,
            "scene_match": scene_match,
            "routed_tag_match": routed_tag_match,
            "priority_norm": round(priority_norm, 4),
            "negation_penalty": 0.30 if negation_conflict else 0.0,
        }
        matched = confidence >= self.MATCH_THRESHOLD and not none_conflict
        return ProtocolMatchResult(
            matched=matched,
            protocol_id=str(protocol.get("protocol_id") or "") or None,
            protocol_name=str(protocol.get("name") or "") or None,
            confidence=round(confidence, 4),
            priority=priority,
            matched_terms=matched_terms,
            body_part_matches=self._dedupe(body_part_matches),
            scene_matches=self._dedupe(scene_matches),
            negation_conflict=negation_conflict,
            reason=reason,
            protocol=protocol if matched else None,
            score_breakdown=score_breakdown,
            threshold=self.MATCH_THRESHOLD,
            active_risks=sorted(active_risks),
            negated_risks=sorted(negated_risks),
            protocol_risks=sorted(protocol_risks),
        )

    def _eval_trigger(
        self, trig: dict[str, Any], text: str, tags: list[str], events: list[str]
    ) -> bool:
        any_of = trig.get("any_of")
        all_of = trig.get("all_of")
        none_of = trig.get("none_of")

        if any_of is None and all_of is None and none_of is None:
            return (
                isinstance(trig, dict)
                and bool(trig)
                and self._match_one(trig, text, tags, events)
            )

        if isinstance(none_of, list) and none_of:
            for cond in none_of:
                if isinstance(cond, dict) and self._match_one(cond, text, tags, events):
                    return False

        if isinstance(all_of, list) and all_of:
            for cond in all_of:
                if not (
                    isinstance(cond, dict) and self._match_one(cond, text, tags, events)
                ):
                    return False
            return True

        if isinstance(any_of, list) and any_of:
            for cond in any_of:
                if isinstance(cond, dict) and self._match_one(cond, text, tags, events):
                    return True
            return False

        return False

    def _match_one(
        self, cond: dict[str, Any], text: str, tags: list[str], events: list[str]
    ) -> bool:
        if "event" in cond:
            return cond["event"] in events

        if "text_contains_any" in cond:
            negatives = cond.get("exclude_words", [])
            has_neg = any(n in text for n in negatives) if negatives else False
            if has_neg:
                return False

            for w in cond["text_contains_any"]:
                if w and w in text:
                    if len(w) == 1 and len(text) < 2 and text != w:
                        continue
                    return True
            return False

        if "tags_any" in cond:
            return any(t in tags for t in cond["tags_any"])

        if "tags_all" in cond:
            return all(t in tags for t in cond["tags_all"])

        return False

    def _extract_text_terms(self, protocol: dict[str, Any]) -> list[str]:
        terms: list[str] = []
        trigger = protocol.get("trigger", {}) or {}
        self._collect_text_terms(trigger, terms, include_none_of=False)
        for key in ("keywords", "keyword", "aliases"):
            value = protocol.get(key)
            if isinstance(value, str):
                terms.append(value)
            elif isinstance(value, list):
                terms.extend(str(item) for item in value if str(item))
        return sorted(self._dedupe(terms), key=len, reverse=True)

    def _collect_text_terms(
        self, value: Any, terms: list[str], *, include_none_of: bool = False
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "none_of" and not include_none_of:
                    continue
                if key in {"text_contains_any", "keywords", "exclude_words"}:
                    if isinstance(item, list):
                        terms.extend(str(x) for x in item if str(x))
                    elif isinstance(item, str):
                        terms.append(item)
                    continue
                self._collect_text_terms(item, terms, include_none_of=include_none_of)
        elif isinstance(value, list):
            for item in value:
                self._collect_text_terms(item, terms, include_none_of=include_none_of)

    def _none_of_conflict(
        self, trigger: dict[str, Any], text: str, routed_tags: list[str], events: list[str]
    ) -> bool:
        none_of = trigger.get("none_of")
        if isinstance(none_of, list):
            for cond in none_of:
                if isinstance(cond, dict) and self._match_one(cond, text, routed_tags, events):
                    return True
        terms: list[str] = []
        self._collect_exclude_words(trigger, terms)
        return any(term in text for term in terms)

    def _collect_exclude_words(self, value: Any, terms: list[str]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "exclude_words":
                    if isinstance(item, list):
                        terms.extend(str(x) for x in item if str(x))
                    elif isinstance(item, str):
                        terms.append(item)
                else:
                    self._collect_exclude_words(item, terms)
        elif isinstance(value, list):
            for item in value:
                self._collect_exclude_words(item, terms)

    def _has_event_match(self, value: Any, events: list[str]) -> bool:
        if isinstance(value, dict):
            if "event" in value and value["event"] in events:
                return True
            return any(self._has_event_match(item, events) for item in value.values())
        if isinstance(value, list):
            return any(self._has_event_match(item, events) for item in value)
        return False

    def _has_tag_match(
        self, trigger: dict[str, Any], routed_tags: list[str], ctx: dict[str, Any]
    ) -> bool:
        intent_tags = [str(x) for x in ctx.get("tags", [])]
        all_tags = set(routed_tags or []) | set(intent_tags)
        return self._trigger_tag_match(trigger, all_tags)

    def _has_protocol_risk_tag_match(
        self, protocol_risks: set[str], routed_tags: list[str], ctx: dict[str, Any]
    ) -> bool:
        intent_tags = {str(x) for x in ctx.get("tags", [])}
        all_tags = set(routed_tags or []) | intent_tags
        for risk in protocol_risks:
            if any(tag in all_tags for tag in INTENT_TAGS.get(risk, ())):
                return True
        return False

    def _trigger_tag_match(self, value: Any, tags: set[str]) -> bool:
        if isinstance(value, dict):
            if "tags_any" in value and any(str(t) in tags for t in value["tags_any"]):
                return True
            if "tags_all" in value and all(str(t) in tags for t in value["tags_all"]):
                return True
            return any(self._trigger_tag_match(item, tags) for item in value.values())
        if isinstance(value, list):
            return any(self._trigger_tag_match(item, tags) for item in value)
        return False

    def _infer_protocol_risks(
        self, protocol: dict[str, Any], matched_terms: list[str]
    ) -> set[str]:
        blob = " ".join(
            [
                str(protocol.get("protocol_id") or ""),
                str(protocol.get("name") or ""),
                " ".join(matched_terms),
            ]
        )
        risks: set[str] = set()
        for intent in INTENT_PRIORITY:
            for term in INTENT_TERMS.get(intent, ()):
                if term and term in blob:
                    risks.add(intent)
                    break
        pid = str(protocol.get("protocol_id") or "").lower()
        if "bleed" in pid or "bleeding" in pid:
            risks.add("severe_bleeding")
        if "breath" in pid or "airway" in pid or "asthma" in pid:
            risks.add("respiratory_distress")
        if "crush" in pid or "trapped" in pid:
            risks.add("trapped_or_crush")
        if "aftershock" in pid or "collapse" in pid:
            risks.add("collapse_aftershock")
        if "head" in pid or "syncope" in pid or "blackout" in pid:
            risks.add("head_or_consciousness")
        if "hypothermia" in pid or "cold" in pid:
            risks.add("hypothermia")
        if "dehydration" in pid or "thirst" in pid:
            risks.add("dehydration")
        if "injury" in pid or "fracture" in pid or "numbness" in pid:
            risks.add("pain_or_injury")
        if "panic" in pid or "claustrophobia" in pid:
            risks.add("panic")
        if "battery" in pid:
            risks.add("low_battery")
        return risks

    def _protocol_mentions(self, protocol: dict[str, Any], term: str) -> bool:
        if not term:
            return False
        return term in json.dumps(protocol, ensure_ascii=False)

    @staticmethod
    def _intent_context_dict(
        intent_context: IntentContext | dict[str, Any] | None,
    ) -> dict[str, Any]:
        if intent_context is None:
            return {}
        if isinstance(intent_context, dict):
            return intent_context
        return intent_context.to_dict()

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out
