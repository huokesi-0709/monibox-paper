"""
monibox/runtime/orchestrator.py

用途
-----
MoniSession 主编排器：组装子模块，协调 handle() 主流程。

M2 重构后，具体职责已分散至：
- text_pipeline.py    → 文本预处理
- output_pipeline.py  → 输出管线（改写、重复抑制、TTS）
- protocol_handler.py → 协议 QA 状态机
- rag_generator.py    → RAG→LLM 生成
- runtime_config.py   → 统一配置
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from monibox.llm.backends import create_llm_backend
from monibox.runtime.emotions import EmotionStrategy, EmotionStrategyBook
from monibox.runtime.evidence_router import LowEvidenceRouter
from monibox.runtime.generator import RagGenerator
from monibox.runtime.guard import SafetyGuard
from monibox.runtime.preprocessor import dedup_sentences, force_second_person, smart_cut
from monibox.runtime.primitives import (
    PerfMonitor,
    RepeatGuard,
    WorkingMemory,
    build_default_variant_bank,
)
from monibox.runtime.protocol_fsm import ProtocolHandler
from monibox.runtime.protocol_matcher import ProtocolEngine
from monibox.runtime.rag_engine import RagEngine, SearchResult
from monibox.runtime.response_pipeline import OutputPipeline
from monibox.runtime.rewriter import ResponseRewriter
from monibox.runtime.runtime_config import load_runtime_config
from monibox.runtime.slot_parser import infer_slot_from_text

# NOTE: TTS 模块延迟加载——纯文本模式无需安装 pyttsx3 / pywin32
try:
    from monibox.tts.pyttsx3 import Pyttsx3TTS
except ImportError:
    Pyttsx3TTS = None  # type: ignore
try:
    from monibox.tts.sapi import SapiTTS  # type: ignore
except Exception:
    SapiTTS = None  # type: ignore
try:
    from monibox.tts.sherpa import SherpaTTS
except ImportError:
    SherpaTTS = None  # type: ignore


# -------------------------
# Session
# -------------------------
@dataclass
class SessionConfig:
    llm_path: str
    llm_ctx: int = 2048
    llm_threads: int = 6
    llm_gpu_layers: int = 0
    tts_enabled: bool = True


class MoniSession:
    """
    清理后的稳定版：
    - 不会出现 prot_noise_ignore 抢走"腿流血"
    - pending -> reask -> protocol match 的顺序固定
    - repeat+variant 真正作用在"播报文本"上
    """

    def __init__(self, rag_db_path: str, cfg: SessionConfig, **kwargs):
        # NOTE: 加载运行时配置（收敛所有 os.getenv）
        self.rt = load_runtime_config()

        # 增加可选的外部注入资源（为了解耦单例架构）
        self.rag = kwargs.get("rag")
        if not self.rag:
            self.rag = RagEngine(rag_db_path)

        self.prot = kwargs.get("protocol_engine") or ProtocolEngine()
        self.guard = kwargs.get("safety_guard") or SafetyGuard()
        self.low_router = kwargs.get("low_evidence_router") or LowEvidenceRouter()
        self.emotions = kwargs.get("emotion_book") or EmotionStrategyBook()
        self.mem = kwargs.get("memory") or WorkingMemory()

        # TTS 初始化
        tts = kwargs.get("tts")
        if tts is None and cfg.tts_enabled:
            # 向后兼容老代码
            if self.rt.tts_backend == "sherpa" and SherpaTTS is not None:
                from monibox.config import resolve_project_path

                model_dir = resolve_project_path(self.rt.tts_sherpa_model_dir)
                tts = SherpaTTS(
                    model_dir=model_dir,
                    model_type=self.rt.tts_sherpa_model_type,
                    num_threads=self.rt.tts_sherpa_threads,
                    cache_size=self.rt.tts_sherpa_cache_size,
                    speed=self.rt.tts_sherpa_speed,
                    sid=self.rt.tts_sherpa_sid,
                    noise_scale=self.rt.tts_sherpa_noise_scale,
                    noise_scale_w=self.rt.tts_sherpa_noise_scale_w,
                )
            elif self.rt.tts_backend == "sapi" and SapiTTS is not None:
                tts = SapiTTS(
                    rate=self.rt.tts_sapi_rate, volume=self.rt.tts_sapi_volume
                )
            elif Pyttsx3TTS is not None:
                tts = Pyttsx3TTS(rate=self.rt.tts_rate, volume=self.rt.tts_volume)

        # LLM + Rewriter
        self.llm = kwargs.get("llm")
        if not self.llm:
            self.llm = create_llm_backend()
        rewriter = ResponseRewriter(self.llm, cfg=self.rt)

        # Variants + Repeat
        vb = build_default_variant_bank()
        repeat_guard = RepeatGuard(threshold=self.rt.repeat_threshold)

        # 组装子模块（支持外部注入以解耦测试）
        self.output = kwargs.get("output_pipeline") or OutputPipeline(
            tts=tts,
            guard=self.guard,
            rewriter=rewriter,
            mem=self.mem,
            vb=vb,
            repeat_guard=repeat_guard,
            cfg=self.rt,
        )
        self.proto_handler = kwargs.get("protocol_handler") or ProtocolHandler(
            guard=self.guard, cfg=self.rt, emotion_book=self.emotions
        )
        self.rag_gen = kwargs.get("rag_generator") or RagGenerator(
            llm=self.llm, cfg=self.rt
        )

        # 挂载性能监控
        self.perf = kwargs.get("perf_monitor") or PerfMonitor(
            warning_mb=self.rt.perf_warning_mb
            if hasattr(self.rt, "perf_warning_mb")
            else 600
        )

        # low-evidence pending
        self.pending_bucket: str | None = None
        self.pending_until: float = 0.0
        self.last_trace: dict[str, Any] = {}
        self.current_interaction_id: str | None = None

    def _set_trace(self, **kwargs) -> None:
        self.last_trace = dict(kwargs)

    # ========== 低证据辅助 ==========

    def _is_low_evidence(self, results: list[SearchResult]) -> bool:
        if not results:
            return True
        best = results[0]
        if best.status == "启用" and float(best.quality_score) >= 5.0:
            return False
        return float(best.distance) > self.rt.rag_max_distance

    def _try_pending_bucket_followup(self, user_text: str) -> tuple | None:
        if not self.pending_bucket:
            return None
        import time

        if time.monotonic() > self.pending_until:
            self.pending_bucket = None
            return None
        from monibox.runtime.slot_parser import parse_yesno

        yn = parse_yesno(user_text)
        if yn is None:
            return None
        bucket = self.pending_bucket
        self.pending_bucket = None
        r = self.low_router.followup(bucket, yes=yn)
        return r.text, bucket

    def _set_pending_bucket_if_needed(self, bucket: str, expect_yesno: bool) -> None:
        if not expect_yesno:
            self.pending_bucket = None
            return
        import time

        self.pending_bucket = bucket
        self.pending_until = time.monotonic() + self.rt.pending_ttl_sec

    def _should_rewrite_low_evidence(self, bucket: str) -> bool:
        return self.rt.rewrite_low_evidence_enabled and bucket not in {"pain"}

    def _low_evidence_emotion(self, user_text: str, bucket: str) -> EmotionStrategy:
        detected = self.emotions.detect(user_text, fallback_stable=False)
        return detected or self.emotions.fallback_for_bucket(bucket)

    def _low_evidence_emit_options(
        self, user_text: str, bucket: str, *, followup: bool = False
    ) -> tuple[EmotionStrategy, int, bool]:
        emotion = self._low_evidence_emotion(user_text, bucket)
        base_limit = (
            self.rt.max_chars_protocol_followup
            if followup
            else self.rt.max_chars_normal
        )
        max_chars = min(base_limit, max(1, emotion.max_chars))
        rewrite_enabled = (
            self._should_rewrite_low_evidence(bucket) and emotion.llm_rewrite_allowed
        )
        return emotion, max_chars, rewrite_enabled

    def _is_localized_pain_query(self, user_text: str) -> bool:
        from monibox.runtime.preprocessor import HIGH_RISK_KEYWORDS, contains_any

        t = user_text or ""
        body_parts = [
            "腿",
            "膝盖",
            "脚",
            "手",
            "胳膊",
            "肩",
            "腰",
            "背",
            "脖子",
            "头",
            "胸口",
        ]
        pain_words = ["痛", "疼", "剧痛", "刺痛"]
        high_risk_override = [
            "胸痛",
            "胸闷",
            "胸口疼",
            "胸口痛",
            "喘不过气",
            "呼吸困难",
            "流血",
            "出血",
            "眼前发黑",
            "要晕",
        ]
        if contains_any(t, HIGH_RISK_KEYWORDS) or any(
            token in t for token in high_risk_override
        ):
            return False
        return any(part in t for part in body_parts) and any(
            word in t for word in pain_words
        )

    # ========== 主编排 ==========

    def handle(
        self, user_text: str, events: list[str] | None = None, auto_top_tags: int = 2
    ) -> str:
        """主入口 Wrapper，用于包裹总耗时和内存监控"""
        self.perf.start_timer("total_handle")
        try:
            return self._handle(user_text, events, auto_top_tags)
        finally:
            total_time = self.perf.end_timer("total_handle")
            mem_mb = self.perf.check_memory(interaction_id=self.current_interaction_id)
            if self.rt.debug_runtime:
                print(
                    f"[PERF] End of Handle. Total Time: {total_time:.2f}s | Mem: {mem_mb:.1f}MB"
                )

    def _handle(
        self, user_text: str, events: list[str] | None = None, auto_top_tags: int = 2
    ) -> str:
        from monibox.runtime.preprocessor import HIGH_RISK_KEYWORDS, contains_any

        events = events or []
        user_text = (user_text or "").strip()
        if not user_text:
            return ""

        self.mem.push_user(user_text)
        rr = self.rag.router.route(user_text, top_tags=auto_top_tags)

        if self._is_localized_pain_query(user_text):
            r = self.low_router.route(user_text)
            emotion, max_chars, rewrite_enabled = self._low_evidence_emit_options(
                user_text, r.bucket
            )
            self._set_pending_bucket_if_needed(r.bucket, r.expect_yesno)
            self._set_trace(
                decision="low_evidence_localized_pain",
                bucket=r.bucket,
                emotion=emotion.emotion,
            )
            if self.rt.debug_runtime:
                print(
                    f"[LOW_EVIDENCE_ROUTE] bucket={r.bucket} (localized-pain-short-circuit)"
                )
            return self.output.emit(
                r.text,
                max_chars=max_chars,
                high_risk=False,
                rewrite_enabled=rewrite_enabled,
                variant_key=f"low:{r.bucket}:main",
                fallback_followup="你先别硬动疼的地方。哪里最痛，或者有没有发麻变形？",
                style=emotion.tts_style,
            )

        # 1) protocol match（高优抢占判断）
        hit = self.prot.match(user_text, rr.tags, events)
        hit_priority = int(hit.get("priority", 0) or 0) if hit else -1

        current_priority = -1
        if self.proto_handler.pending_protocol and isinstance(
            self.proto_handler.pending_protocol.get("proto"), dict
        ):
            current_priority = int(
                self.proto_handler.pending_protocol["proto"].get("priority", 0) or 0
            )
        elif self.proto_handler.active_protocol and isinstance(
            self.proto_handler.active_protocol.get("proto"), dict
        ):
            current_priority = int(
                self.proto_handler.active_protocol["proto"].get("priority", 0) or 0
            )

        # NOTE: 抢占逻辑——新协议优先级 > 当前等待优先级时，强制打断
        # 同级不打断（比如同样是 95 的出血协议，不互相打断）
        preempted = False
        if hit and hit_priority > current_priority and current_priority > 0:
            if self.rt.debug_runtime:
                print(
                    f"[PREEMPTION] New protocol {hit.get('protocol_id')} (p={hit_priority}) preempts current (p={current_priority})"
                )
            self.proto_handler.clear_state()
            self.pending_bucket = None
            preempted = True

        # 2) pending answer（如果没有发生抢占）
        if not preempted:
            got = self.proto_handler.try_pending_answer(user_text)
            if got:
                text, pid = got
                self._set_trace(decision="protocol_pending_answer", protocol_id=pid)
                return self.output.emit(
                    text,
                    max_chars=self.rt.max_chars_protocol_followup,
                    high_risk=True,
                    rewrite_enabled=self.rt.rewrite_protocol_enabled,
                    variant_key=f"protocol:{pid}:followup",
                    fallback_followup="你现在能回答我刚才那个问题吗？",
                    style="urgent_calm",
                )

            pending_soft = self.proto_handler.handle_pending_soft_interruption(
                user_text
            )
            if pending_soft:
                text, pid = pending_soft
                self._set_trace(decision="protocol_pending_soft", protocol_id=pid)
                return self.output.emit(
                    text,
                    max_chars=self.rt.max_chars_protocol_followup,
                    high_risk=True,
                    rewrite_enabled=False,
                    variant_key=f"protocol:{pid}:followup",
                    fallback_followup="先回答我刚才那个问题。",
                    style="urgent_calm",
                )

            pending_noise = self.proto_handler.handle_pending_noise(user_text)
            if pending_noise:
                text, pid = pending_noise
                self._set_trace(decision="protocol_pending_noise", protocol_id=pid)
                return self.output.emit(
                    text,
                    max_chars=self.rt.max_chars_protocol_followup,
                    high_risk=True,
                    rewrite_enabled=self.rt.rewrite_protocol_enabled,
                    variant_key=f"protocol:{pid}:followup",
                    fallback_followup="先回答我刚才那个问题。",
                    style="urgent_calm",
                )

            # 3) pending reask
            reask = self.proto_handler.maybe_reask(user_text)
            if reask:
                self._set_trace(decision="protocol_reask")
                return self.output.emit(
                    reask,
                    max_chars=self.rt.max_chars_protocol_followup,
                    high_risk=True,
                    rewrite_enabled=self.rt.rewrite_protocol_enabled,
                    variant_key="generic:reask",
                    fallback_followup="再说一遍也行，短一点没关系。",
                    style="warm",
                )

            # 4) bucket pending
            bf = self._try_pending_bucket_followup(user_text)
            if bf:
                text, bucket = bf
                emotion, max_chars, rewrite_enabled = self._low_evidence_emit_options(
                    "", bucket, followup=True
                )
                self._set_trace(
                    decision="low_evidence_followup",
                    bucket=bucket,
                    emotion=emotion.emotion,
                )
                return self.output.emit(
                    text,
                    max_chars=max_chars,
                    high_risk=False,
                    rewrite_enabled=rewrite_enabled,
                    variant_key=f"low:{bucket}:followup",
                    fallback_followup="你现在哪里最不舒服？",
                    style=emotion.tts_style,
                )

            # 5) active freeform（short answer only）
            act = self.proto_handler.try_active_freeform(user_text)
            if act:
                text, pid = act
                self._set_trace(decision="protocol_active_freeform", protocol_id=pid)
                return self.output.emit(
                    text,
                    max_chars=self.rt.max_chars_protocol_followup,
                    high_risk=True,
                    rewrite_enabled=self.rt.rewrite_protocol_enabled,
                    variant_key=f"protocol:{pid}:followup",
                    fallback_followup="你现在能回答我刚才的问题吗？",
                    style="urgent_calm",
                )

        # 6) execute protocol match
        if hit:
            pid = str(hit.get("protocol_id") or "")
            self.proto_handler.set_active(pid, hit)

            actions, is_followup, step = self.proto_handler.pick_actions(hit)
            tts_texts = self.proto_handler.extract_tts_texts(actions)

            out_lines: list[str] = []
            last_q: str | None = None
            for txt in tts_texts:
                gr = self.guard.check(txt)
                safe = gr.safe_text
                out_lines.append(safe)
                if infer_slot_from_text(safe) is not None:
                    last_q = safe

            base = smart_cut(
                dedup_sentences(force_second_person(" ".join(out_lines))),
                self.rt.max_chars_protocol_main,
            )

            if self.rt.debug_runtime:
                print(
                    "\n[PROTOCOL HIT]",
                    pid,
                    hit.get("name"),
                    f"followup={is_followup}",
                    f"step={step}",
                )
                print("[FINAL]", base)

            self._set_trace(
                decision="protocol_main",
                protocol_id=pid,
                protocol_name=hit.get("name"),
                priority=int(hit.get("priority", 0) or 0),
                preempted=preempted,
                followup=is_followup,
                step=step,
            )
            spoken = self.output.emit(
                base,
                max_chars=self.rt.max_chars_protocol_main,
                high_risk=int(hit.get("priority", 0) or 0) >= 80,
                rewrite_enabled=self.rt.rewrite_protocol_enabled,
                variant_key=f"protocol:{pid}:main",
                fallback_followup="你现在情况有变化吗？",
                style="urgent_calm"
                if int(hit.get("priority", 0) or 0) >= 50
                else "calm",
            )

            if last_q:
                self.proto_handler.set_pending(pid, hit, last_q)
            else:
                self.proto_handler.pending_protocol = None

            return spoken

        # 7) active freeform（抢占后的第二次检查）
        act = self.proto_handler.try_active_freeform(user_text)
        if act:
            text, pid = act
            self._set_trace(
                decision="protocol_active_freeform_post_preempt", protocol_id=pid
            )
            return self.output.emit(
                text,
                max_chars=self.rt.max_chars_protocol_followup,
                high_risk=True,
                rewrite_enabled=self.rt.rewrite_protocol_enabled,
                variant_key=f"protocol:{pid}:followup",
                fallback_followup="你现在能回答我刚才的问题吗？",
                style="urgent_calm",
            )

        if self.rt.low_evidence_mode and self.rag.is_vague_query(user_text):
            r = self.low_router.route(user_text)
            emotion, max_chars, rewrite_enabled = self._low_evidence_emit_options(
                user_text, r.bucket
            )
            self._set_pending_bucket_if_needed(r.bucket, r.expect_yesno)
            self._set_trace(
                decision="low_evidence_vague", bucket=r.bucket, emotion=emotion.emotion
            )
            if self.rt.debug_runtime:
                print(f"[LOW_EVIDENCE_ROUTE] bucket={r.bucket} (vague-short-circuit)")

            return self.output.emit(
                r.text,
                max_chars=max_chars,
                high_risk=False,
                rewrite_enabled=rewrite_enabled,
                variant_key=f"low:{r.bucket}:main",
                fallback_followup="你身上有受伤吗？出血或疼痛的话先说。",
                style=emotion.tts_style,
            )

        # 8) RAG search -> low evidence deterministic
        dim = None if rr.cross_dimension else rr.dimension
        results = self.rag.search(
            user_text, topk=6, pool_mult=8, dimension=dim, tags=rr.tags, max_per_group=1
        )
        if not results:
            results = self.rag.search(
                user_text,
                topk=6,
                pool_mult=8,
                dimension=None,
                tags=None,
                max_per_group=1,
            )

        low_evidence = self._is_low_evidence(results)

        if self.rt.debug_runtime:
            if results:
                print(
                    f"[RAG] best.distance={results[0].distance:.4f} best.final_distance={results[0].final_distance:.4f} low_evidence={low_evidence}"
                )
            else:
                print(f"[RAG] no results low_evidence={low_evidence}")

        if self.rt.low_evidence_mode and low_evidence:
            r = self.low_router.route(user_text)
            emotion, max_chars, rewrite_enabled = self._low_evidence_emit_options(
                user_text, r.bucket
            )
            self._set_pending_bucket_if_needed(r.bucket, r.expect_yesno)
            self._set_trace(
                decision="low_evidence_rag_fallback",
                bucket=r.bucket,
                emotion=emotion.emotion,
            )
            if self.rt.debug_runtime:
                print(f"[LOW_EVIDENCE_ROUTE] bucket={r.bucket}")

            return self.output.emit(
                r.text,
                max_chars=max_chars,
                high_risk=False,
                rewrite_enabled=rewrite_enabled,
                variant_key=f"low:{r.bucket}:main",
                fallback_followup="你身上有受伤吗？出血或疼痛的话先说。",
                style=emotion.tts_style,
            )

        self.perf.start_timer("rag_gen")
        # 9) Normal mode: RAG 检索结果 → LLM 生成回复
        high_risk = contains_any(user_text, HIGH_RISK_KEYWORDS)

        if getattr(self.rt, "llm_stream", False):
            full_reply = ""
            for sentence in self.rag_gen.stream_sentences(
                user_text, results, high_risk, self.mem
            ):
                if not sentence.strip():
                    continue
                spoken = self.output.emit_stream_sentence(sentence, style="warm")
                if spoken:
                    full_reply += spoken + " "

            reply = full_reply.strip()
            self.mem.push_bot(reply)

            # 流式结束时统计耗时
            elapsed_llm = self.perf.end_timer("rag_gen")
            if self.rt.debug_runtime:
                print(f"[PERF] RAG Gen (Stream) Took {elapsed_llm:.2f}s")

            return reply

        # 非流式回退
        reply = self.rag_gen.generate(user_text, results, high_risk, self.mem)
        elapsed_llm = self.perf.end_timer("rag_gen")
        if self.rt.debug_runtime:
            print(f"[PERF] RAG Gen (Bulk) Took {elapsed_llm:.2f}s")

        top_chunk_id = results[0].chunk_id if results else None
        self._set_trace(
            decision="rag_normal",
            top_chunk_id=top_chunk_id,
            low_evidence=False,
            result_count=len(results),
        )
        return self.output.emit(
            reply,
            max_chars=self.rt.max_chars_normal,
            high_risk=high_risk,
            rewrite_enabled=self.rt.rewrite_low_evidence_enabled,
            variant_key="rag:normal:main",
            fallback_followup="你身上有受伤吗？出血、疼痛或喘不过气的话告诉我。",
            style="warm",
        )
