"""
monibox/runtime/preprocessor.py

用途
-----
文本预处理管道：负责所有文本截断、清理、改写成第二人称的预处理操作。
从原 session.py 中剥离，降低 MoniSession 的职责耦合。
"""

from __future__ import annotations

import re
from typing import Any

from monibox.json_parser import extract_first_json

# NOTE: 高危关键词列表，用于判断用户输入是否涉及紧急医疗场景
HIGH_RISK_KEYWORDS = [
    "流血",
    "出血",
    "喷血",
    "止不住",
    "断了",
    "骨折",
    "折了",
    "变形",
    "动不了",
    "剧痛",
    "眼前发黑",
    "要晕",
    "站不稳",
    "喘不过气",
    "呼吸困难",
    "窒息",
]


def normalize_for_tts(text: str) -> str:
    """清理空白字符，适配 TTS 输出"""
    t = (text or "").strip().replace("\r", " ").replace("\n", " ")
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip()


def smart_cut(text: str, max_chars: int) -> str:
    """
    智能断句截断：优先在句末标点处截断，避免断在句中
    """
    t = normalize_for_tts(text)
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    m = max(
        cut.rfind("。"),
        cut.rfind("！"),
        cut.rfind("？"),
        cut.rfind("."),
        cut.rfind("!"),
        cut.rfind("?"),
    )
    if m >= 10:
        return cut[: m + 1].strip()
    return cut.strip()


def force_second_person(t: str) -> str:
    """强制第二人称替换：将"我的手/脚/腿/眼睛"替换为"你的..." """
    s = normalize_for_tts(t)
    return (
        s.replace("我的手", "你的手")
        .replace("我的脚", "你的脚")
        .replace("我的腿", "你的腿")
        .replace("我的眼睛", "你的眼睛")
    )


def dedup_sentences(t: str) -> str:
    """相邻重复句去重：防止同一句话被重复拼接"""
    s = normalize_for_tts(t)
    parts = re.split(r"([。！？!?])", s)
    out = []
    last = None
    for i in range(0, len(parts), 2):
        seg = (parts[i] or "").strip()
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if not seg:
            continue
        if last is not None and seg == last:
            continue
        out.append(seg + punct)
        last = seg
    return "".join(out).strip()


def split_sentences(text: str) -> list[str]:
    """按句末标点切句，保留标点，供 TTS 选句和收敛节奏使用。"""
    s = normalize_for_tts(text)
    if not s:
        return []

    parts = re.split(r"([。！？!?；;])", s)
    out: list[str] = []
    for i in range(0, len(parts), 2):
        seg = (parts[i] or "").strip()
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if not seg:
            continue
        out.append(f"{seg}{punct}".strip())
    return out


def is_question_sentence(sentence: str) -> bool:
    """粗略判断一句话是不是澄清/追问句。"""
    s = normalize_for_tts(sentence)
    if not s:
        return False
    if "？" in s or "?" in s:
        return True

    question_hints = (
        "吗",
        "么",
        "呢",
        "哪儿",
        "哪里",
        "什么",
        "谁",
        "多久",
        "有没有",
        "是否",
        "能不能",
        "可不可以",
        "要不要",
    )
    return any(hint in s for hint in question_hints)


def shape_tts_text(text: str, max_chars: int) -> str:
    """
    将输出尽量收敛成“一个动作句 + 一个追问句”。
    这样能减少机械感，也更贴近阶段 D 的 TTS 听感目标。
    """
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) == 1:
        return smart_cut(sentences[0], max_chars)

    question = next((s for s in sentences if is_question_sentence(s)), "")
    non_questions = [s for s in sentences if s != question]
    meaningful = [s for s in non_questions if len(s.strip("。！？!?，,；; ")) > 6]
    action = (
        meaningful[0]
        if meaningful
        else (non_questions[0] if non_questions else sentences[0])
    )

    picked: list[str] = []
    for sentence in (action, question):
        if sentence and sentence not in picked:
            picked.append(sentence)

    for sentence in sentences:
        if len(picked) >= 2:
            break
        if sentence not in picked:
            picked.append(sentence)

    shaped = dedup_sentences("".join(picked))
    if len(shaped) <= max_chars:
        return shaped

    if question and action and question != action:
        kept_question = smart_cut(question, min(len(question), max(12, max_chars // 2)))
        action_budget = max(12, max_chars - len(kept_question))
        kept_action = smart_cut(action, action_budget)
        merged = dedup_sentences(f"{kept_action}{kept_question}")
        return smart_cut(merged, max_chars)

    return smart_cut(shaped, max_chars)


def contains_any(text: str, words: list[str]) -> bool:
    """检查文本中是否包含任一关键词"""
    return any(w and w in text for w in words)


def parse_llm_payload(raw: str) -> dict[str, Any]:
    """
    解析 LLM 返回的 JSON 格式输出。
    兼容 {text, ask, used_ids} 格式，解析失败时回退为原始文本。
    """
    raw = (raw or "").strip()
    if not raw:
        return {"ok": False, "text": "", "used_ids": [], "ask": ""}

    try:
        obj = extract_first_json(raw)
        if not isinstance(obj, dict):
            return {"ok": False, "text": raw, "used_ids": [], "ask": ""}

        text = str(obj.get("text", "") or "")
        ask = str(obj.get("ask", "") or "")
        used_ids = obj.get("used_ids", []) or []
        if isinstance(used_ids, str):
            used_ids = [used_ids]
        if not isinstance(used_ids, list):
            used_ids = []
        used_ids = [str(x) for x in used_ids if str(x).strip()]

        return {"ok": True, "text": text, "used_ids": used_ids, "ask": ask}
    except Exception:
        return {"ok": False, "text": raw, "used_ids": [], "ask": ""}


def normalize_payload(text: str, ask: str) -> str:
    """
    合并 text 和 ask 字段，去重后统一第二人称。
    避免 ask 与 text 内容重复。
    """
    t = normalize_for_tts(text)
    a = normalize_for_tts(ask)
    if a and (a == t or a in t or t in a):
        a = ""
    merged = (t + (" " + a if a else "")).strip()
    merged = force_second_person(merged)
    return dedup_sentences(merged)
