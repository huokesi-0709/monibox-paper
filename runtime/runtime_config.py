"""
runtime/runtime_config.py

用途
-----
运行时配置中心：将散落在 session.py、response_rewriter.py 等模块中的
os.getenv 调用统一收敛到一处，便于管理、测试和后续端侧部署调参。

设计决策
--------
- 构建侧配置（DeepSeek API、Embedding 模型、RAG DB 路径等）仍由
  config.py 管理，本模块只管运行时行为。
- 使用 dataclass + 工厂函数，支持测试时注入自定义值。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

PROFILE_ENV = "RUNTIME_PROFILE"
PROFILE_PATH_ENV = "RUNTIME_CONFIG_PATH"

_PROFILE_FIELD_ALIASES = {
    "tts_model_dir": "tts_sherpa_model_dir",
    "tts_model_type": "tts_sherpa_model_type",
    "tts_threads": "tts_sherpa_threads",
    "cache_size": "tts_sherpa_cache_size",
    "enable_llm_rewrite": "rewrite_enabled",
}

_ENV_FIELD_MAP = {
    "RAG_MAX_DISTANCE": "rag_max_distance",
    "LOW_EVIDENCE_MODE": "low_evidence_mode",
    "PENDING_TTL_SEC": "pending_ttl_sec",
    "PROTOCOL_QA_TTL_SEC": "protocol_qa_ttl_sec",
    "ACTIVE_PROTOCOL_TTL_SEC": "active_protocol_ttl_sec",
    "PROTOCOL_DEFAULT_COOLDOWN_SEC": "protocol_default_cooldown_sec",
    "PROTOCOL_GENERIC_FOLLOWUP": "protocol_generic_followup",
    "REWRITE_PROTOCOL_ENABLED": "rewrite_protocol_enabled",
    "REWRITE_LOW_EVIDENCE_ENABLED": "rewrite_low_evidence_enabled",
    "REWRITE_MAX_CHARS_PROTOCOL_MAIN": "max_chars_protocol_main",
    "REWRITE_MAX_CHARS_PROTOCOL_FOLLOWUP": "max_chars_protocol_followup",
    "REWRITE_MAX_CHARS_NORMAL": "max_chars_normal",
    "REWRITE_ENABLED": "rewrite_enabled",
    "ENABLE_LLM_REWRITE": "rewrite_enabled",
    "REWRITE_TEMPERATURE": "rewrite_temperature",
    "REWRITE_TOP_P": "rewrite_top_p",
    "TTS_MAX_CHARS": "tts_max_chars",
    "TTS_BACKEND": "tts_backend",
    "TTS_RATE": "tts_rate",
    "TTS_VOLUME": "tts_volume",
    "TTS_SAPI_RATE": "tts_sapi_rate",
    "TTS_SAPI_VOLUME": "tts_sapi_volume",
    "TTS_SHERPA_MODEL_DIR": "tts_sherpa_model_dir",
    "TTS_SHERPA_MODEL_TYPE": "tts_sherpa_model_type",
    "TTS_SHERPA_THREADS": "tts_sherpa_threads",
    "TTS_SHERPA_CACHE_SIZE": "tts_sherpa_cache_size",
    "TTS_SHERPA_SPEED": "tts_sherpa_speed",
    "TTS_SHERPA_SID": "tts_sherpa_sid",
    "TTS_SHERPA_NOISE_SCALE": "tts_sherpa_noise_scale",
    "TTS_SHERPA_NOISE_SCALE_W": "tts_sherpa_noise_scale_w",
    "LLM_CTX": "llm_ctx",
    "LLM_THREADS": "llm_threads",
    "LLM_GPU_LAYERS": "llm_gpu_layers",
    "LLM_TEMPERATURE": "llm_temperature",
    "LLM_STREAM": "llm_stream",
    "REPEAT_THRESHOLD": "repeat_threshold",
    "VARIANT_MODE": "variant_mode",
    "ENABLE_LED": "enable_led",
    "ENABLE_SCREEN": "enable_screen",
    "ENABLE_PRECOMPUTED_AUDIO": "enable_precomputed_audio",
    "DEBUG_RUNTIME": "debug_runtime",
    "DEBUG_TTS": "debug_tts",
    "PERF_WARNING_MB": "perf_warning_mb",
}


@dataclass
class RuntimeConfig:
    """运行时所有可调参数的单一数据类"""

    # ---- RAG 检索 ----
    rag_max_distance: float = 0.42
    low_evidence_mode: bool = True

    # ---- 协议 TTL ----
    pending_ttl_sec: float = 15.0
    protocol_qa_ttl_sec: float = 25.0
    active_protocol_ttl_sec: float = 45.0
    protocol_default_cooldown_sec: float = 20.0
    protocol_generic_followup: str = (
        "我在。你现在情况有没有变化？有出血或呼吸困难马上告诉我。"
    )

    # ---- 润色/改写 ----
    rewrite_protocol_enabled: bool = True
    rewrite_low_evidence_enabled: bool = True
    max_chars_protocol_main: int = 78
    max_chars_protocol_followup: int = 65
    max_chars_normal: int = 90
    rewrite_enabled: bool = True
    rewrite_temperature: float = 0.2
    rewrite_top_p: float = 0.9

    # ---- TTS ----
    tts_max_chars: int = 90
    tts_backend: str = "sherpa"
    tts_rate: int = 180
    tts_volume: float = 1.0
    tts_sapi_rate: int = 0
    tts_sapi_volume: int = 100
    tts_sherpa_model_dir: str = "models/tts/sherpa/vits-icefall-zh-aishell3"
    tts_sherpa_model_type: str = "melo"
    tts_sherpa_threads: int = 4
    tts_sherpa_cache_size: int = 100
    tts_sherpa_speed: float = 0.92
    tts_sherpa_sid: int = 173
    tts_sherpa_noise_scale: float = 0.72
    tts_sherpa_noise_scale_w: float = 0.85

    # ---- LLM ----
    llm_ctx: int = 2048
    llm_threads: int = 6
    llm_gpu_layers: int = 0
    llm_temperature: float = 0.3
    llm_stream: bool = False

    # ---- 硬件 / 降级画像 ----
    enable_led: bool = True
    enable_screen: bool = True
    enable_precomputed_audio: bool = False

    # ---- 重复抑制 ----
    repeat_threshold: float = 0.92
    variant_mode: str = "rr"

    # ---- 调试 ----
    debug_runtime: bool = False
    debug_tts: bool = False
    perf_warning_mb: int = 600


def _strip_inline_comment(value: str) -> str:
    """Remove simple YAML-style comments while keeping quoted values intact."""
    quote: str | None = None
    for i, ch in enumerate(value):
        if ch in {"'", '"'}:
            quote = None if quote == ch else ch
        elif ch == "#" and quote is None:
            return value[:i].strip()
    return value.strip()


def _parse_scalar(raw: str) -> Any:
    value = _strip_inline_comment(raw)
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    try:
        if "." not in value:
            return int(value)
        return float(value)
    except ValueError:
        return value


def _coerce_like(value: Any, default: Any) -> Any:
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int) and not isinstance(default, bool):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return str(value).strip()


def _resolve_profile_path(profile: str | None) -> Path | None:
    explicit_path = (os.getenv(PROFILE_PATH_ENV, "") or "").strip()
    if explicit_path:
        path = Path(explicit_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    name = (profile or os.getenv(PROFILE_ENV, "windows") or "windows").strip()
    if not name or name.lower() in {"none", "off", "0"}:
        return None

    path = Path(name)
    if path.suffix in {".yaml", ".yml"} or path.parent != Path("."):
        return path if path.is_absolute() else PROJECT_ROOT / path

    primary = PROJECT_ROOT / "profiles" / f"{name}.yaml"
    if primary.exists():
        return primary
    return PROJECT_ROOT / "profiles" / f"{name}.yaml"


def _load_profile_values(profile: str | None) -> dict[str, Any]:
    path = _resolve_profile_path(profile)
    if path is None or not path.exists():
        return {}

    values: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        field_name = _PROFILE_FIELD_ALIASES.get(key.strip(), key.strip())
        values[field_name] = _parse_scalar(raw_value)
    return values


def load_runtime_config(profile: str | None = None) -> RuntimeConfig:
    """
    从环境变量一次性加载所有运行时配置。
    每个字段都有合理的默认值，缺失环境变量不会报错。

    优先级：
    1. 环境变量 / .env
    2. profiles/*.yaml
    3. RuntimeConfig 代码默认值
    """
    defaults = RuntimeConfig()
    values = {
        field.name: getattr(defaults, field.name) for field in fields(RuntimeConfig)
    }

    for key, raw_value in _load_profile_values(profile).items():
        if key in values:
            values[key] = _coerce_like(raw_value, values[key])

    for env_key, field_name in _ENV_FIELD_MAP.items():
        if env_key in os.environ and field_name in values:
            values[field_name] = _coerce_like(os.getenv(env_key), values[field_name])

    values["tts_backend"] = str(values["tts_backend"]).strip().lower()
    values["tts_sherpa_model_type"] = (
        str(values["tts_sherpa_model_type"]).strip().lower()
    )
    values["variant_mode"] = str(values["variant_mode"]).strip().lower()
    return RuntimeConfig(**values)
