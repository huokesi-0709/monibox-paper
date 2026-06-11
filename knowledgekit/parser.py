"""
utils_json.py

把 LLM 输出尽可能稳定地解析成 JSON（Python对象）
"""

import json
import re
from typing import Any

try:
    import json5
except ImportError:
    json5 = None


def strip_fences(text: str) -> str:
    t = (text or "").strip()
    # 去掉 ```json
    t = re.sub(r"^\s*```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    # 去掉 ```
    t = re.sub(r"\s*```\s*$", "", t, flags=re.IGNORECASE)
    return t.strip()


def first_start(s: str) -> int | None:
    for i, ch in enumerate(s):
        if ch in "{[":
            return i
    return None


def last_end(s: str) -> int | None:
    for i in range(len(s) - 1, -1, -1):
        if s[i] in "}]":
            return i
    return None


def repair_unclosed_brackets(s: str) -> str:
    """
    自动补齐未闭合的括号。忽略字符串内部括号。
    例如：{"a":[{"b":1}   -> 自动补成 {"a":[{"b":1}]}
    """
    stack = []
    in_str = False
    escape = False

    for ch in s:
        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            top = stack[-1]
            if (top == "{" and ch == "}") or (top == "[" and ch == "]"):
                stack.pop()
            else:
                # 括号类型不匹配，忽略（可选 json5 会继续兜底）
                pass

    closing = []
    while stack:
        top = stack.pop()
        closing.append("}" if top == "{" else "]")
    return s + "".join(closing)


def _try_parse_json(block: str) -> Any:
    """strict json + optional json5 两段兜底解析。"""
    try:
        return json.loads(block)
    except Exception as strict_error:
        if json5 is None:
            raise strict_error
        try:
            return json5.loads(block)
        except Exception as json5_error:
            raise json5_error from strict_error


def _find_first_balanced_json_block(t: str) -> str | None:
    """
    在文本中找到"第一个完整闭合"的 JSON 块（对象或数组），忽略字符串内部括号。
    用于处理：{...}\n{...}\n{...} 这种多段 JSON 输出。
    """
    st = first_start(t)
    if st is None:
        return None

    stack = []
    in_str = False
    escape = False

    for i in range(st, len(t)):
        ch = t[i]

        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            top = stack[-1]
            if (top == "{" and ch == "}") or (top == "[" and ch == "]"):
                stack.pop()
                if not stack:
                    # st..i 是第一个完整 JSON 块
                    return t[st : i + 1].strip()

    return None


def extract_first_json(text: str) -> Any:
    """
    优先解析"第一个完整闭合 JSON 块"。

    适用场景：
    - 模型输出多个 JSON：{...}\n{...}\n{...}
    - 模型前后夹杂文字，但第一个 JSON 是完整的

    失败时会退回到 extract_json 的"截取大块 + 补括号"策略。
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM 返回空字符串（可能网络错误/被限流/请求失败）")

    t = strip_fences(raw)

    fallback_error: Exception | None = None
    block = _find_first_balanced_json_block(t)
    if block:
        try:
            return _try_parse_json(block)
        except Exception as first_block_error:
            # 若这个完整块仍不严格，则继续走老策略（更激进的修复）
            fallback_error = first_block_error

    # 回退：用原 extract_json 的策略
    try:
        return extract_json(text)
    except Exception as extract_error:
        if fallback_error is not None:
            raise extract_error from fallback_error
        raise


def extract_json(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM 返回空字符串（可能网络错误/被限流/请求失败）")

    t = strip_fences(raw)

    # 1) 先 strict 直接解析
    try:
        return json.loads(t)
    except Exception as direct_error:
        first_error = direct_error

    # 2) 截取 JSON 大块
    st = first_start(t)
    ed = last_end(t)
    if st is None or ed is None or ed <= st:
        raise ValueError(f"无法定位JSON块。输出前200字符：{t[:200]!r}")

    block = t[st : ed + 1].strip()

    # 3) 尝试自动补齐括号（解决"截断"）
    block2 = repair_unclosed_brackets(block)

    # 4) strict 再试
    try:
        return json.loads(block2)
    except Exception as repaired_error:
        first_error = repaired_error

    # 5) optional json5 兜底（允许单引号/尾逗号/未加引号 key）
    if json5 is not None:
        try:
            return json5.loads(block2)
        except Exception as e:
            first_error = e

    raise ValueError(
        "JSON解析失败（strict json 与 optional json5 都失败或 json5 未安装）。\n"
        f"错误：{first_error}\n"
        f"候选JSON块前200字符：{block2[:200]!r}\n"
        f"候选JSON块后200字符：{block2[-200:]!r}"
    ) from first_error


# ---------- text_clean (migrated from text_clean.py) ----------


def clean_text(s: str) -> str:
    """基础清洗：空白规范化。"""
    return re.sub(r"\s+", " ", s).strip()
