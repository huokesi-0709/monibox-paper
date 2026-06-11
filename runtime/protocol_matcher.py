from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


class ProtocolEngine:
    """
    协议引擎：
    - 兼容 protocols.json 顶层 list 或 dict({"protocols":[...]})
    - priority 降序匹配
    - 自动按 protocol_id 去重（保留 priority 更高的；priority 相同保留更靠前的）
    """

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
                    "protocols.json 顶层是对象(dict)，但未找到 key='protocols' 的数组。\n"
                    f"keys={list(data.keys())}"
                )
        else:
            raise ValueError(
                f"protocols.json 顶层必须是 list 或 dict。实际：{type(data)}"
            )

        protos = [p for p in protos if isinstance(p, dict)]

        # priority 降序排序（稳定排序：相同priority保持原顺序）
        protos = sorted(
            protos, key=lambda p: int(p.get("priority", 0) or 0), reverse=True
        )

        # 自动去重：保留第一次出现的 protocol_id（此时已按 priority 降序）
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
            # 仅提示，不中断运行
            uniq = sorted(set(dup_list))
            print(
                f"[ProtocolEngine] WARNING: duplicated protocol_id detected and deduped: {uniq}"
            )

        self.protocols = deduped

    def match(
        self, text: str, routed_tags: list[str], events: list[str]
    ) -> dict[str, Any] | None:
        text = text or ""
        routed_tags = routed_tags or []
        events = events or []

        for p in self.protocols:
            trig = p.get("trigger", {}) or {}
            if self._eval_trigger(trig, text, routed_tags, events):
                return p
        return None

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
                    # 对于单字，保留“完全相等”的明确触发词（如“喂”），
                    # 但仍避免把任意短噪声都当成命中。
                    if len(w) == 1 and len(text) < 2 and text != w:
                        continue
                    return True
            return False

        if "tags_any" in cond:
            return any(t in tags for t in cond["tags_any"])

        if "tags_all" in cond:
            return all(t in tags for t in cond["tags_all"])

        return False
