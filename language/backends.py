"""
language/backends.py

统一 LLM 接口 —— 通过 LLM_BACKEND 环境变量选择后端：
  - "deepseek"：调用 DeepSeek API（开发阶段，Windows 首选）
  - "llama"   ：调用本地 llama.cpp（部署阶段，Radxa 首选）
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMBackend(ABC):
    """统一的 LLM 调用接口"""

    @abstractmethod
    def generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> str:
        """生成回复，返回纯文本字符串"""
        ...

    @abstractmethod
    def stream_generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> Iterator[str]:
        """流式生成，每次 yield 一个 token 字符串"""
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str: ...


class NullLLMBackend(LLMBackend):
    """
    无模型回退后端。
    用于测试、文本主链调试或尚未配置真实 LLM 的场景。
    """

    def generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> str:
        return ""

    def stream_generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> Iterator[str]:
        if False:
            yield ""

    @property
    def backend_name(self) -> str:
        return "null"


class DeepSeekBackend(LLMBackend):
    """DeepSeek API 后端（开发阶段用）"""

    def __init__(self) -> None:
        from openai import OpenAI

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = os.getenv("DEEPSEEK_MODEL_CHAT", "deepseek-chat")

        if not api_key:
            raise RuntimeError("LLM_BACKEND=deepseek 但未设置 DEEPSEEK_API_KEY")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    def stream_generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> Iterator[str]:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in resp:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    @property
    def backend_name(self) -> str:
        return f"deepseek({self._model})"


class LlamaCppBackend(LLMBackend):
    """llama.cpp 本地模型后端（部署阶段用）"""

    def __init__(
        self,
        gguf_path: str,
        n_ctx: int = 2048,
        n_threads: int = 6,
        n_gpu_layers: int = 0,
    ) -> None:
        from language.local import LlamaCppChat, LLMConfig

        self._llm = LlamaCppChat(
            LLMConfig(
                gguf_path=gguf_path,
                n_ctx=n_ctx,
                n_threads=n_threads,
                n_gpu_layers=n_gpu_layers,
            )
        )
        self._gguf_path = gguf_path

    def generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> str:
        return self._llm.generate_chat(
            system, user, max_tokens=max_tokens, temperature=temperature
        )

    def stream_generate(
        self, system: str, user: str, max_tokens: int = 120, temperature: float = 0.3
    ) -> Iterator[str]:
        return self._llm.stream_chat(
            system, user, max_tokens=max_tokens, temperature=temperature
        )

    @property
    def backend_name(self) -> str:
        import pathlib

        return f"llama({pathlib.Path(self._gguf_path).name})"


def create_llm_backend() -> LLMBackend:
    """
    根据 LLM_BACKEND 环境变量创建对应后端。
    默认：若未设置 LLM_GGUF_PATH 则用 deepseek，否则用 llama。
    """
    from runtime.runtime_config import load_runtime_config

    rt = load_runtime_config()
    backend = (os.getenv("LLM_BACKEND", "auto") or "auto").strip().lower()

    gguf_path = os.getenv("LLM_GGUF_PATH", "")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")

    if backend == "auto":
        # NOTE: 自动模式：
        # 1. 有 GGUF 文件 -> llama
        # 2. 有 DeepSeek Key -> deepseek
        # 3. 都没有 -> null（便于测试与文本主链调试）
        if gguf_path:
            backend = "llama"
        elif deepseek_api_key:
            backend = "deepseek"
        else:
            backend = "null"

    if backend == "deepseek":
        return DeepSeekBackend()
    if backend == "llama":
        if not gguf_path:
            raise RuntimeError("LLM_BACKEND=llama 但未设置 LLM_GGUF_PATH")
        return LlamaCppBackend(
            gguf_path=gguf_path,
            n_ctx=rt.llm_ctx,
            n_threads=rt.llm_threads,
            n_gpu_layers=rt.llm_gpu_layers,
        )
    if backend == "null":
        return NullLLMBackend()
    raise ValueError(
        f"未知的 LLM_BACKEND: {backend!r}，可选值: deepseek, llama, auto, null"
    )
