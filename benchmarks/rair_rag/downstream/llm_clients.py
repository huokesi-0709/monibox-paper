from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCAL_MODEL_PATH = "models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf"
DEFAULT_REFERENCE_MODEL = "qwen2.5-7b-instruct"


class BaseGenerator(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass
class LocalLlamaCppGenerator(BaseGenerator):
    model_path: str | Path | None = None
    n_ctx: int | None = None
    n_threads: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    seed: int | None = None
    verbose: bool = False
    stop: list[str] = field(default_factory=list)
    _llm: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.model_path = resolve_model_path(
            self.model_path
            or os.getenv("LOCAL_LLM_MODEL_PATH")
            or DEFAULT_LOCAL_MODEL_PATH
        )
        self.n_ctx = int(
            self.n_ctx if self.n_ctx is not None else _env_int("LOCAL_LLM_N_CTX", 2048)
        )
        self.n_threads = int(
            self.n_threads
            if self.n_threads is not None
            else _env_int("LOCAL_LLM_N_THREADS", 4)
        )
        self.temperature = float(
            self.temperature
            if self.temperature is not None
            else _env_float("LOCAL_LLM_TEMPERATURE", 0.2)
        )
        self.top_p = float(
            self.top_p if self.top_p is not None else _env_float("LOCAL_LLM_TOP_P", 0.9)
        )
        self.max_tokens = int(
            self.max_tokens
            if self.max_tokens is not None
            else _env_int("LOCAL_LLM_MAX_TOKENS", 512)
        )
        self.seed = int(
            self.seed if self.seed is not None else _env_int("LOCAL_LLM_SEED", 42)
        )
        self._ensure_model_file()

    def generate(self, prompt: str) -> str:
        text = str(prompt or "").strip()
        if not text:
            return ""
        llm = self._load_model()
        result = llm(
            text,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=self.stop or None,
        )
        return _completion_text(result)

    def _load_model(self) -> Any:
        if self._llm is not None:
            return self._llm
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            msg = (
                "llama-cpp-python is not installed. "
                "Please install it with `uv sync --extra local-llm`."
            )
            raise RuntimeError(msg) from exc

        self._ensure_model_file()
        self._llm = Llama(
            model_path=str(self.model_path),
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            seed=self.seed,
            verbose=self.verbose,
        )
        return self._llm

    def _ensure_model_file(self) -> None:
        path = Path(self.model_path)
        if path.exists():
            return
        msg = (
            f"Local GGUF model file not found: {path}. "
            "Place Qwen1.5-0.5B-Chat-Q4_K_M at "
            "`models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf`, or set "
            "LOCAL_LLM_MODEL_PATH to the correct GGUF path."
        )
        raise FileNotFoundError(msg)


@dataclass
class ReferenceApiGenerator(BaseGenerator):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url or os.getenv("REFERENCE_LLM_BASE_URL") or None
        self.api_key = self.api_key or os.getenv("REFERENCE_LLM_API_KEY") or None
        self.model = (
            self.model or os.getenv("REFERENCE_LLM_MODEL") or DEFAULT_REFERENCE_MODEL
        )
        self.temperature = float(
            self.temperature
            if self.temperature is not None
            else _env_float("REFERENCE_LLM_TEMPERATURE", 0.2)
        )
        self.top_p = float(
            self.top_p
            if self.top_p is not None
            else _env_float("REFERENCE_LLM_TOP_P", 0.9)
        )
        self.max_tokens = int(
            self.max_tokens
            if self.max_tokens is not None
            else _env_int("REFERENCE_LLM_MAX_TOKENS", 512)
        )
        if not self.api_key:
            msg = (
                "REFERENCE_LLM_API_KEY is not set. Set it in your environment "
                "before using the reference-llm generator; do not commit API keys."
            )
            raise RuntimeError(msg)

    def generate(self, prompt: str) -> str:
        text = str(prompt or "").strip()
        if not text:
            return ""
        client = self._load_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": text}],
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
        )
        return _chat_completion_text(response)

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            msg = "openai is not installed. Run `uv sync` before using reference-llm."
            raise RuntimeError(msg) from exc

        kwargs: dict[str, str] = {"api_key": str(self.api_key)}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client


def resolve_model_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return (PROJECT_ROOT / resolved).resolve()


def _completion_text(result: Any) -> str:
    if isinstance(result, dict):
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                return str(first.get("text") or "").strip()
        return str(result.get("text") or "").strip()
    return str(result).strip()


def _chat_completion_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        content = getattr(message, "content", None)
        if content:
            return str(content).strip()
    if isinstance(response, dict):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    return str(message.get("content") or "").strip()
                return str(first.get("text") or "").strip()
    return str(response).strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)
