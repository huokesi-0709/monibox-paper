from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from monibox.config import KNOWLEDGE_SRC
from monibox.tags.tag_registry import TagRegistry

CATEGORY_FIELD = "知识类别"
CANONICAL_CATEGORY_FIELD = "category"
SUBCATEGORY_FIELD = "二级子类"
CANONICAL_SUBCATEGORY_FIELD = "sub_category"

DEFAULT_CATEGORY = "evaluation_case"
DEFAULT_SUBCATEGORY = "unclassified"


def load_category_spec(path: Path | None = None) -> dict[str, Any]:
    spec_path = path or (KNOWLEDGE_SRC / "knowledge_category_spec.json")
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("knowledge_category_spec.json 根节点必须是对象")
    return data


def allowed_categories(spec: dict[str, Any] | None = None) -> set[str]:
    spec = spec or load_category_spec()
    return {
        str(item.get("category") or "").strip()
        for item in spec.get("categories", [])
        if isinstance(item, dict) and str(item.get("category") or "").strip()
    }


def load_subcategory_spec(path: Path | None = None) -> dict[str, Any]:
    spec_path = path or (KNOWLEDGE_SRC / "knowledge_subcategory_spec.json")
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("knowledge_subcategory_spec.json 根节点必须是对象")
    return data


def allowed_subcategories(spec: dict[str, Any] | None = None) -> set[str]:
    spec = spec or load_subcategory_spec()
    return {
        str(item.get("sub_category") or "").strip()
        for item in spec.get("subcategories", [])
        if isinstance(item, dict) and str(item.get("sub_category") or "").strip()
    }


def infer_category(chunk: dict[str, Any], spec: dict[str, Any] | None = None) -> str:
    existing = str(
        chunk.get(CATEGORY_FIELD) or chunk.get(CANONICAL_CATEGORY_FIELD) or ""
    ).strip()
    spec = spec or load_category_spec()
    categories = allowed_categories(spec)
    if existing in categories:
        return existing

    tags = [str(tag).strip() for tag in chunk.get("标签", []) or [] if str(tag).strip()]
    text = " ".join(
        [
            str(chunk.get("维度") or ""),
            str(chunk.get("子主题") or ""),
            str(chunk.get("文本") or ""),
            " ".join(tags),
        ]
    )

    def has_tag_prefix(*prefixes: str) -> bool:
        return any(tag.startswith(prefix) for tag in tags for prefix in prefixes)

    def has_keyword(*keywords: str) -> bool:
        return any(keyword in text for keyword in keywords)

    if has_keyword("求救", "信号", "敲击", "哨子", "手电", "定位"):
        return "rescue_signal"
    if has_tag_prefix("env_", "sec_", "scn_") or has_keyword(
        "余震", "坍塌", "粉尘", "灰", "水淹", "洪水", "低温", "寒冷"
    ):
        return "environment_hazard"
    if has_tag_prefix("spc_") or has_keyword(
        "儿童", "老人", "老年", "糖尿病", "哮喘", "心脏病", "幽闭恐惧"
    ):
        return "special_population"
    if has_tag_prefix("med_"):
        return "medical_risk"
    if has_tag_prefix("psy_") or has_keyword(
        "恐慌", "害怕", "绝望", "内疚", "自责", "愤怒"
    ):
        return "psychological_support"
    if has_keyword("追问", "澄清", "低证据", "拒答", "回拉", "降温"):
        return "conversation_control"
    if has_tag_prefix("tts_") or has_keyword("播报", "停顿", "短句"):
        return "tts_expression"
    if has_tag_prefix("hw_") or has_keyword("LED", "屏幕", "提示音"):
        return "hardware_feedback"

    return DEFAULT_CATEGORY


def infer_subcategory(chunk: dict[str, Any], spec: dict[str, Any] | None = None) -> str:
    existing = str(
        chunk.get(SUBCATEGORY_FIELD) or chunk.get(CANONICAL_SUBCATEGORY_FIELD) or ""
    ).strip()
    spec = spec or load_subcategory_spec()
    subcategories = allowed_subcategories(spec)
    if existing in subcategories:
        return existing

    raw_tags = [
        str(tag).strip() for tag in chunk.get("标签", []) or [] if str(tag).strip()
    ]
    try:
        registry = TagRegistry.load()
        tags = registry.canonicalize_list(raw_tags)
        tag_lookup = set(tags) | set(raw_tags)
    except Exception:
        registry = None
        tags = raw_tags
        tag_lookup = set(raw_tags)

    text = " ".join(
        [
            str(chunk.get("维度") or ""),
            str(chunk.get("子主题") or ""),
            str(chunk.get("文本") or ""),
            str(chunk.get("问题") or ""),
            " ".join(tags),
        ]
    )

    best_subcategory = DEFAULT_SUBCATEGORY
    best_score = 0.0
    for item in spec.get("subcategories", []):
        if not isinstance(item, dict):
            continue
        sub_category = str(item.get("sub_category") or "").strip()
        if not sub_category:
            continue

        score = 0.0
        for tag_id in item.get("tag_ids") or []:
            raw_tag_id = str(tag_id).strip()
            candidates = {raw_tag_id}
            if registry is not None:
                canon = registry.canonicalize(raw_tag_id)
                if canon:
                    candidates.add(canon)
            if candidates & tag_lookup:
                score += 4.0
        for term in item.get("trigger_terms") or []:
            term = str(term).strip()
            if term and term in text:
                score += 1.0 + min(len(term), 8) * 0.08

        if score > best_score:
            best_score = score
            best_subcategory = sub_category

    return best_subcategory


def enrich_chunk_category(
    chunk: dict[str, Any], spec: dict[str, Any] | None = None
) -> dict[str, Any]:
    category = infer_category(chunk, spec)
    chunk[CATEGORY_FIELD] = category
    chunk[CANONICAL_CATEGORY_FIELD] = category
    return chunk


def enrich_chunk_subcategory(
    chunk: dict[str, Any], spec: dict[str, Any] | None = None
) -> dict[str, Any]:
    sub_category = infer_subcategory(chunk, spec)
    chunk[SUBCATEGORY_FIELD] = sub_category
    chunk[CANONICAL_SUBCATEGORY_FIELD] = sub_category
    return chunk

