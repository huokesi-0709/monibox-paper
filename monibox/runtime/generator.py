"""
monibox/runtime/generator.py

用途
-----
RAG 生成器：将 RAG 检索结果作为上下文，调用 LLM 生成回复。
实现三级回退：LLM JSON 成功 → LLM 原始输出 → 最佳 chunk 原文。
从原 session.py._generate_from_rag 剥离。
"""

from __future__ import annotations

from collections.abc import Iterator

from monibox.llm.backends import LLMBackend
from monibox.runtime.rag_engine import SearchResult
from monibox.runtime.runtime_config import RuntimeConfig
from monibox.runtime.primitives import WorkingMemory
from monibox.runtime.preprocessor import (
    dedup_sentences,
    force_second_person,
    normalize_payload,
    parse_llm_payload,
    smart_cut,
)


class RagGenerator:
    """
    将检索到的知识片段 + 用户提问发给 LLM，生成口语化回复。
    三级回退策略确保即使 LLM 出错也有可用输出。
    """

    def __init__(self, llm: LLMBackend, cfg: RuntimeConfig):
        self.llm = llm
        self.cfg = cfg

    def generate(
        self,
        user_text: str,
        results: list[SearchResult],
        high_risk: bool,
        memory: WorkingMemory | None = None,
    ) -> str:
        """
        将 RAG 检索结果作为上下文，调用 LLM 生成回复。
        三级回退：LLM 成功 → LLM 原始输出 → 最佳 chunk 原文
        """
        if not results:
            return "我在。你现在最不舒服的是哪里？"

        # NOTE: 组装知识片段上下文，最多取 top-5
        context_lines = []
        for r in results[:5]:
            context_lines.append(f"- {r.text}")
        context = "\n".join(context_lines)

        # 挂载对话历史
        history_text = ""
        if memory and memory.history:
            recent_hist = list(memory.history)[-3:]
            hist_lines = []
            for h_u, h_b in recent_hist:
                if h_u:
                    hist_lines.append(f"用户: {h_u}")
                if h_b:
                    hist_lines.append(f"摩尼: {h_b}")
            if hist_lines:
                history_text = "【最近对话回顾】\n" + "\n".join(hist_lines) + "\n\n"

        system_prompt = (
            '你是"摩尼"，一个陪伴地震受困者的声音助手。\n'
            "\n"
            "【你的风格】\n"
            "- 像一个冷静、温柔但坚定的朋友在身边\n"
            '- 用"你"而不是"您"\n'
            "- 说话简短有力，一到两句话，不超过60字\n"
            "- 给出一个具体可执行的动作指令\n"
            "- 末尾可以追问一个简短的确认问题\n"
            "\n"
            "【绝对禁止】\n"
            "- 诊断疾病或给药物剂量\n"
            '- 说"马上就能获救"\n'
            '- 用"请尽量""如果可能"等推脱语气\n'
            '- 说"保持冷静"等空话套话\n'
            "- 超过60个字\n"
            "\n"
            f"{history_text}"
            "【参考规则与建议行动（优先使用）】\n"
            f"{context}\n"
            "\n"
            "只输出回复文本，不要输出JSON或其他格式。"
        )

        if self.cfg.debug_runtime:
            print(f"\n[RAG→LLM] context chunks={len(results[:5])}")
            for r in results[:3]:
                print(f"  [{r.display_id}] d={r.distance:.3f} {r.text[:40]}...")

        try:
            raw = self.llm.generate(
                system_prompt,
                user_text,
                max_tokens=120,
                temperature=self.cfg.llm_temperature,
            )
            raw = (raw or "").strip()

            if self.cfg.debug_runtime:
                print(f"[RAG→LLM] raw={raw[:80]}...")

            # NOTE: 优先尝试 JSON 格式解析（兼容旧 prompt 风格）
            if "{" in raw:
                payload = parse_llm_payload(raw)
                if payload["ok"] and payload["text"].strip():
                    reply = normalize_payload(payload["text"], payload["ask"])
                    if reply.strip():
                        return reply

            # NOTE: 非 JSON 格式，直接使用 LLM 输出
            if raw and len(raw) >= 4:
                cleaned = force_second_person(dedup_sentences(raw))
                return smart_cut(cleaned, self.cfg.max_chars_normal)

        except Exception as e:
            if self.cfg.debug_runtime:
                print(f"[RAG→LLM] ERROR: {e}")

        # NOTE: LLM 失败时回退到最佳 chunk 原文
        return results[0].text

    def stream_sentences(
        self,
        user_text: str,
        results: list[SearchResult],
        high_risk: bool,
        memory: WorkingMemory | None = None,
    ) -> Iterator[str]:
        """流式分句生成：一边从 LLM 获取 token，一边按标点切分出句子 yield 给外部"""
        if not results:
            yield "我在。你现在最不舒服的是哪里？"
            return

        context = "\n".join(f"- {r.text}" for r in results[:5])

        # 挂载对话历史
        history_text = ""
        if memory and memory.history:
            recent_hist = list(memory.history)[-3:]
            hist_lines = []
            for h_u, h_b in recent_hist:
                if h_u:
                    hist_lines.append(f"用户: {h_u}")
                if h_b:
                    hist_lines.append(f"摩尼: {h_b}")
            if hist_lines:
                history_text = "【最近对话回顾】\n" + "\n".join(hist_lines) + "\n\n"

        system_prompt = (
            '你是"摩尼"，一个陪伴地震受困者的声音助手。\n'
            "\n"
            "【你的风格】\n"
            "- 像一个冷静、温柔但坚定的朋友在身边\n"
            '- 用"你"而不是"您"\n'
            "- 说话简短有力，一到两句话，不超过60字\n"
            "- 给出一个具体可执行的动作指令\n"
            "- 末尾可以追问一个简短的确认问题\n"
            "\n"
            "【绝对禁止】\n"
            "- 诊断疾病或给药物剂量\n"
            '- 说"马上就能获救"\n'
            '- 用"请尽量""如果可能"等推脱语气\n'
            '- 说"保持冷静"等空话套话\n'
            "- 超过60个字\n"
            "\n"
            f"{history_text}"
            "【参考规则与建议行动（优先使用）】\n"
            f"{context}\n"
            "\n"
            "只输出回复文本，不要输出JSON或其他格式。"
        )

        sentence = ""
        try:
            for tok in self.llm.stream_generate(
                system_prompt,
                user_text,
                max_tokens=120,
                temperature=self.cfg.llm_temperature,
            ):
                sentence += tok
                if any(p in tok for p in ["。", "！", "？", "!", "?", "\n"]):
                    if sentence.strip():
                        yield sentence.strip()
                    sentence = ""
            if sentence.strip():
                yield sentence.strip()
        except Exception as e:
            if self.cfg.debug_runtime:
                print(f"[RAG->LLM STREAM] ERROR: {e}")
            yield results[0].text
