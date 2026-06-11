"""
monibox/runtime/response_rewriter.py

用途
-----
受控润色器：只润色表达，不改含义；不合格就回退原文。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from monibox.llm.backend import LLMBackend
from monibox.utils_json import extract_first_json

if TYPE_CHECKING:
    from monibox.runtime.runtime_config import RuntimeConfig


def _normalize(s: str) -> str:
    return (s or "").strip().replace("\r", " ").replace("\n", " ")


def _smart_cut(text: str, max_chars: int) -> str:
    t = _normalize(text)
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


def _dedup_sentences(t: str) -> str:
    s = _normalize(t)
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


@dataclass
class RewriteResult:
    text: str
    used_fallback: bool
    reason: str = ""


class ResponseRewriter:
    def __init__(self, llm: LLMBackend, cfg: RuntimeConfig | None = None):
        self.llm = llm
        # NOTE: 优先从 RuntimeConfig 读取配置，未传入时回退到 os.getenv（向后兼容）
        if cfg is not None:
            self.enabled = cfg.rewrite_enabled
            self.temp = cfg.rewrite_temperature
            self.top_p = cfg.rewrite_top_p
        else:
            self.enabled = os.getenv("REWRITE_ENABLED", "1") == "1"
            self.temp = float(os.getenv("REWRITE_TEMPERATURE", "0.2"))
            self.top_p = float(os.getenv("REWRITE_TOP_P", "0.9"))

    def _fails_hard_rules(
        self, cand: str, high_risk: bool, avoid_repeat: list[str]
    ) -> str | None:
        t = _normalize(cand)

        # 禁止电话号码/剂量等
        banned_sub = [
            "120",
            "110",
            "毫克",
            "mg",
            "ml",
            "手术",
            "注射",
            "剂量",
            "确诊",
            "诊断",
        ]
        if any(x in t for x in banned_sub):
            return "banned_token"

        # 高风险：严禁第一人称自伤/自述
        if high_risk and (
            "我的" in t
            or "我正在" in t
            or "我最" in t
            or "我不舒服" in t
            or "我无法" in t
        ):
            return "first_person_high_risk"

        # 避免把最近 bot 话术又粘回来
        for x in avoid_repeat[:3]:
            x = _normalize(x)
            if len(x) >= 8 and x in t:
                return "repeat_recent_bot"

        return None

    def rewrite(
        self,
        base_text: str,
        max_chars: int,
        avoid_repeat: list[str] | None = None,
        high_risk: bool = False,
    ) -> RewriteResult:
        base = _smart_cut(base_text, max_chars)
        avoid_repeat = avoid_repeat or []

        if not self.enabled:
            return RewriteResult(
                text=_dedup_sentences(base),
                used_fallback=True,
                reason="rewrite_disabled",
            )

        # 如果是本地端侧模型，禁用 LLM 润色，改为快速规则替换
        if getattr(self.llm, "backend_name", "").startswith("llama"):
            return self._rule_based_rewrite(base, max_chars, high_risk, avoid_repeat)

        system = (
            "你是一个中文润色器，只做轻量润色，让口语更自然。\n"
            "绝对规则：不改变含义；不新增建议；不新增归因；不输出电话号码；不输出诊断/剂量。\n"
            '只输出一个 JSON：{"text":"..."}，不要输出其他内容。\n'
            f"输出长度 <= {max_chars} 字，尽量 1-2 句。\n"
            "永远用第二人称（你/你的），不要出现“我的/我正在/我最不舒服”。\n"
        )

        user = f"原句：{base}\n"
        if avoid_repeat:
            user += (
                "避免重复这些说法（不要原样粘贴）：\n"
                + "\n".join([f"- {x}" for x in avoid_repeat[:3]])
                + "\n"
            )

        raw = self.llm.generate(system, user, max_tokens=180, temperature=self.temp)

        try:
            obj = extract_first_json(raw)
            cand = str(obj.get("text", "") or "").strip()
        except Exception:
            return RewriteResult(
                text=_dedup_sentences(base),
                used_fallback=True,
                reason="json_parse_fail",
            )

        cand = _dedup_sentences(_smart_cut(cand, max_chars))

        reason = self._fails_hard_rules(
            cand, high_risk=high_risk, avoid_repeat=avoid_repeat
        )
        if reason:
            return RewriteResult(
                text=_dedup_sentences(base), used_fallback=True, reason=reason
            )

        # 过度漂移保护（字符集合 Jaccard）
        sa, sb = set(base), set(cand)
        j = len(sa & sb) / max(1, len(sa | sb))
        if j < (0.65 if high_risk else 0.55):
            return RewriteResult(
                text=_dedup_sentences(base),
                used_fallback=True,
                reason=f"too_far:j={j:.2f}",
            )

        return RewriteResult(text=cand, used_fallback=False, reason="ok")

    def _rule_based_rewrite(
        self, base: str, max_chars: int, high_risk: bool, avoid_repeat: list[str]
    ) -> RewriteResult:
        """极速本地规则润色：仅用正则/字符串替换，耗时极低"""
        t = base

        # 尊称和不适当从句剥离
        t = t.replace("请您", "你")
        t = t.replace("您", "你")
        t = t.replace("根据我们所了解的情况，", "")
        t = t.replace("根据您的描述，", "")
        t = t.replace("请千万", "一定要")
        t = t.replace("请尽快", "快点")

        t = _dedup_sentences(_smart_cut(t, max_chars))

        reason = self._fails_hard_rules(
            t, high_risk=high_risk, avoid_repeat=avoid_repeat
        )
        if reason:
            return RewriteResult(
                text=_dedup_sentences(base), used_fallback=True, reason=f"rule_{reason}"
            )

        return RewriteResult(text=t, used_fallback=False, reason="rule_ok")
