from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCAL_MODEL_PATH = "models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf"
DEFAULT_REFERENCE_PROVIDER = "dashscope_openai"
DEFAULT_REFERENCE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_REFERENCE_MODEL = "qwen-plus"
DEFAULT_REFERENCE_TOP_P = 0.8
DEFAULT_REFERENCE_TIMEOUT_SECONDS = 120
DEFAULT_REFERENCE_MAX_RETRIES = 2
LOCAL_CHAT_MODES = {"chat_completion", "qwen_manual", "completion"}
LOCAL_QWEN_SYSTEM_PROMPT = (
    "You are a concise safety-critical emergency assistant. Output valid JSON only."
)
LOCAL_QWEN_STOP_TOKENS = ["<|im_end|>", "<|endoftext|>"]


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
    chat_mode: str | None = None
    verbose: bool = False
    stop: list[str] = field(default_factory=list)
    _llm: Any = field(default=None, init=False, repr=False)
    last_reason: str = field(default="", init=False)
    last_chat_mode: str = field(default="", init=False)

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
        self.chat_mode = (
            self.chat_mode or os.getenv("LOCAL_LLM_CHAT_MODE") or "chat_completion"
        )
        if self.chat_mode not in LOCAL_CHAT_MODES:
            allowed = ", ".join(sorted(LOCAL_CHAT_MODES))
            msg = f"unsupported LOCAL_LLM_CHAT_MODE {self.chat_mode!r}; choose one of {allowed}"
            raise ValueError(msg)
        self.stop = _merge_stop_tokens(self.stop)
        self._ensure_model_file()

    def generate(self, prompt: str) -> str:
        text = str(prompt or "").strip()
        self.last_reason = ""
        self.last_chat_mode = str(self.chat_mode or "")
        if not text:
            return ""
        llm = self._load_model()
        if self.chat_mode == "completion":
            return self._generate_completion(llm, text)
        if self.chat_mode == "qwen_manual":
            return self._generate_qwen_manual(llm, text)
        try:
            return self._generate_chat_completion(llm, text)
        except Exception:
            return self._generate_qwen_manual(llm, text)

    def _generate_chat_completion(self, llm: Any, prompt: str) -> str:
        if not hasattr(llm, "create_chat_completion"):
            raise AttributeError("llama-cpp-python create_chat_completion is unavailable")
        self.last_chat_mode = "chat_completion"
        result = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": LOCAL_QWEN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=self.stop,
        )
        output = _choice_text(result)
        if not output:
            self.last_reason = "empty_generation_after_chat_template"
        return output

    def _generate_qwen_manual(self, llm: Any, prompt: str) -> str:
        self.last_chat_mode = "qwen_manual"
        result = llm(
            qwen_chat_prompt(prompt),
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=self.stop,
        )
        output = _choice_text(result)
        if not output:
            self.last_reason = "empty_generation_after_chat_template"
        return output

    def _generate_completion(self, llm: Any, prompt: str) -> str:
        self.last_chat_mode = "completion"
        result = llm(
            prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=self.stop,
        )
        output = _choice_text(result)
        if not output:
            self.last_reason = "empty_generation_after_completion"
        return output

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
    timeout_seconds: float | None = None
    max_retries: int | None = None
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = (
            self.base_url
            or os.getenv("REFERENCE_LLM_BASE_URL")
            or DEFAULT_REFERENCE_BASE_URL
        )
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
            else _env_float("REFERENCE_LLM_TOP_P", DEFAULT_REFERENCE_TOP_P)
        )
        self.max_tokens = int(
            self.max_tokens
            if self.max_tokens is not None
            else _env_int("REFERENCE_LLM_MAX_TOKENS", 512)
        )
        self.timeout_seconds = float(
            self.timeout_seconds
            if self.timeout_seconds is not None
            else _env_float(
                "REFERENCE_LLM_TIMEOUT_SECONDS", DEFAULT_REFERENCE_TIMEOUT_SECONDS
            )
        )
        self.max_retries = int(
            self.max_retries
            if self.max_retries is not None
            else _env_int("REFERENCE_LLM_MAX_RETRIES", DEFAULT_REFERENCE_MAX_RETRIES)
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

        kwargs: dict[str, Any] = {
            "api_key": str(self.api_key),
            "timeout": self.timeout_seconds,
            "max_retries": self.max_retries,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client


def resolve_model_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return (PROJECT_ROOT / resolved).resolve()


def qwen_chat_prompt(prompt: str) -> str:
    return (
        "<|im_start|>system\n"
        f"{LOCAL_QWEN_SYSTEM_PROMPT}\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"{prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def _completion_text(result: Any) -> str:
    return _choice_text(result)


def _choice_text(result: Any) -> str:
    choices = getattr(result, "choices", None)
    if choices:
        return _choice_item_text(choices[0])
    if isinstance(result, dict):
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            return _choice_item_text(choices[0])
        return str(result.get("text") or "").strip()
    return str(result).strip()


def _choice_item_text(first: Any) -> str:
    message = getattr(first, "message", None)
    content = getattr(message, "content", None)
    if content:
        return str(content).strip()
    text = getattr(first, "text", None)
    if text:
        return str(text).strip()
    if isinstance(first, dict):
        message = first.get("message")
        if isinstance(message, dict):
            return str(message.get("content") or "").strip()
        return str(first.get("text") or "").strip()
    return ""


def _chat_completion_text(response: Any) -> str:
    return _choice_text(response)


def _merge_stop_tokens(stop: list[str]) -> list[str]:
    merged = list(stop or [])
    for token in LOCAL_QWEN_STOP_TOKENS:
        if token not in merged:
            merged.append(token)
    return merged


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
