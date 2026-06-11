"""
monibox/runtime/output_pipeline.py

用途
-----
输出管线：负责文本后处理、改写润色、重复抑制、TTS 播报的完整输出流水线。
从原 session.py 中剥离 _postprocess_text, _speak, _emit, _maybe_rewrite,
_apply_repeat_and_variants 等方法。
"""

from __future__ import annotations

import re

from monibox.runtime.memory import WorkingMemory
from monibox.runtime.repeat_guard import RepeatGuard
from monibox.runtime.response_rewriter import ResponseRewriter
from monibox.runtime.runtime_config import RuntimeConfig
from monibox.runtime.safety_guard import SafetyGuard
from monibox.runtime.text_pipeline import (
    dedup_sentences,
    force_second_person,
    normalize_for_tts,
    shape_tts_text,
    smart_cut,
)
from monibox.runtime.variants import VariantBank


class OutputPipeline:
    """
    统一输出管线，封装从"原始文本"到"安全播报"的全部步骤：
    后处理 → 改写 → 重复抑制/变体替换 → 第二人称强制 → 安全护栏 → TTS 播报
    """

    def __init__(
        self,
        tts: object | None,
        guard: SafetyGuard,
        rewriter: ResponseRewriter,
        mem: WorkingMemory,
        vb: VariantBank,
        repeat_guard: RepeatGuard,
        cfg: RuntimeConfig,
    ):
        self.tts = tts
        self.guard = guard
        self.rewriter = rewriter
        self.mem = mem
        self.vb = vb
        self.repeat_guard = repeat_guard
        self.cfg = cfg
        self._turn_context: dict = {}

    def set_turn_context(self, metadata: dict | None) -> None:
        self._turn_context = dict(metadata or {})

    def postprocess_text(self, text: str, max_chars: int) -> str:
        """清理标点并收敛成更适合播报的短句形状。"""
        t = (text or "").strip()
        if not t:
            return ""
        t = re.sub(r"\.{2,}|…{2,}|。{2,}", "。", t)
        t = normalize_for_tts(t)
        return shape_tts_text(t, max_chars)

    def speak(self, text: str, style: str | None = None) -> None:
        """
        调用 TTS 播报（阻塞式）。
        当前默认使用 Sherpa-ONNX 173 号音色，支持 urgent/calm 等样式。
        """
        if not self.cfg.tts_backend or self.tts is None:
            return
        t = self.postprocess_text(text, self.cfg.tts_max_chars)
        if not t:
            return
        if self.cfg.debug_tts:
            print(f"[TTS style={style}] start:", t)

        meta = dict(self._turn_context)
        meta["tts_text"] = t
        meta["tts_style"] = style
        self.tts.speak(t, block=True, style=style, metadata=meta)

        if self.cfg.debug_tts:
            print("[TTS] done")

    def maybe_rewrite(
        self, base: str, max_chars: int, high_risk: bool, enabled: bool
    ) -> str:
        """条件润色：开启时调用 ResponseRewriter，失败回退原文"""
        base2 = smart_cut(dedup_sentences(force_second_person(base)), max_chars)
        if not enabled:
            return base2
        res = self.rewriter.rewrite(
            base_text=base2,
            max_chars=max_chars,
            avoid_repeat=self.mem.last_bot_texts(3),
            high_risk=high_risk,
        )
        if self.cfg.debug_runtime:
            print(
                "[REWRITE] ok"
                if not res.used_fallback
                else f"[REWRITE] fallback reason={res.reason}"
            )
        out = re.sub(r"\.{2,}|…{2,}|。{2,}", "。", res.text)
        return out

    def apply_repeat_and_variants(
        self, text: str, variant_key: str, fallback_followup: str
    ) -> str:
        """重复抑制 + 变体替换：检测到重复时用变体库替换播报文本"""
        cand = (text or "").strip()
        recent = self.mem.last_bot_texts(3)
        dec = self.repeat_guard.decide(cand, recent)
        if not dec.is_repeat:
            return cand

        mode = self.cfg.variant_mode
        # NOTE: 优先选"长度接近"的变体，避免感觉只读半句
        variants = self.vb.variants.get(variant_key) or []
        if variants:
            target_len = len(cand)
            close = sorted(variants, key=lambda s: abs(len(s) - target_len))
            v = (
                close[0]
                if close
                else self.vb.pick(variant_key, default=cand, mode=mode)
            )
        else:
            v = self.vb.pick(variant_key, default=cand, mode=mode)

        dec2 = self.repeat_guard.decide(v, recent)
        if not dec2.is_repeat:
            return v

        return (fallback_followup or v or cand).strip()

    def emit(
        self,
        text: str,
        *,
        max_chars: int,
        high_risk: bool,
        rewrite_enabled: bool,
        variant_key: str,
        fallback_followup: str,
        style: str | None = None,
    ) -> str:
        """
        完整输出流水线入口：
        改写 → 去重/变体 → 第二人称强制 → 安全护栏 → TTS → 记忆
        """
        t = self.maybe_rewrite(
            text, max_chars=max_chars, high_risk=high_risk, enabled=rewrite_enabled
        )
        t = self.apply_repeat_and_variants(
            t, variant_key=variant_key, fallback_followup=fallback_followup
        )

        # 兜底：强制第二人称，避免任何路径出现"我正在流血/我呼吸困难"
        t = force_second_person(t)
        t = re.sub(r"我正在|我最不舒服|我无法|我在流血", "你", t)

        gr = self.guard.check(t)
        out = self.postprocess_text(gr.safe_text, max_chars=max_chars)
        self.speak(out, style=style)
        self.mem.push_bot(out)
        return out

    def emit_stream_sentence(self, sentence: str, style: str | None = None) -> str:
        """
        流式专用的分句安全检查和播报，不走去重和改写，直接播报。
        不会被推入记忆（由外部调用方收集完完整段落后再推入记忆）。
        """
        t = force_second_person(sentence)
        t = re.sub(r"我正在|我最不舒服|我无法|我在流血", "你", t)

        gr = self.guard.check(t)
        # 流式单句不强制截断 (999)
        out = self.postprocess_text(gr.safe_text, max_chars=999)
        if out:
            self.speak(out, style=style)
        return out
