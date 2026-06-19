"""
runtime/runtime_config.py

用途
-----
运行时配置中心。本模块在重构后保留向后兼容的 facade：
- 内部实际配置源已迁移到 app.settings（Pydantic + YAML 分层体系）
- RuntimeConfig dataclass 与 load_runtime_config() 签名保持不变
- 现有调用方无需立即修改

加载优先级（新体系）：
    profiles/base.yaml（默认值）
        ↓ merge
    profiles/{platform}.yaml（差异覆盖）
        ↓ Pydantic 校验
    MoniboxSettings 对象
        ↓ .env 注入
    最终配置（含 API Key 等机密）

迁移说明
--------
- 新增参数请直接改 profiles/base.yaml 或各平台 yaml，不要再加 os.getenv
- .env 仅保留机密（DEEPSEEK_API_KEY 等）
- 如需层级访问新配置，可直接 import app.settings
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.settings import MoniboxSettings, load_settings

PROFILE_ENV = "RUNTIME_PROFILE"
PROFILE_PATH_ENV = "RUNTIME_CONFIG_PATH"

# 保留向后兼容的别名映射（新体系下不再扩展，仅维护存量）
_PROFILE_FIELD_ALIASES = {
    "tts_model_dir": "tts_sherpa_model_dir",
    "tts_model_type": "tts_sherpa_model_type",
    "tts_threads": "tts_sherpa_threads",
    "cache_size": "tts_sherpa_cache_size",
    "enable_llm_rewrite": "rewrite_enabled",
}

# 保留向后兼容的环境变量映射（新参数请走 YAML，不要在此新增）
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
    "RUNTIME_TRACE_ENABLED": "runtime_trace_enabled",
    "RUNTIME_TRACE_PATH": "trace_path",
    "DEBUG_RUNTIME": "debug_runtime",
    "DEBUG_TTS": "debug_tts",
    "PERF_WARNING_MB": "perf_warning_mb",
}


@dataclass
class RuntimeConfig:
    """运行时所有可调参数的单一数据类（向后兼容）"""

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
    llm_backend: str = "auto"
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
    runtime_trace_enabled: bool = True
    trace_path: str = "build/runtime_logs/interaction_trace.jsonl"
    debug_runtime: bool = False
    debug_tts: bool = False
    perf_warning_mb: int = 600


def _settings_to_flat(cfg: MoniboxSettings) -> dict[str, Any]:
    """将层级 MoniboxSettings 扁平化为 RuntimeConfig 兼容的键值对。"""
    return {
        # RAG
        "rag_max_distance": cfg.rag.max_distance,
        "low_evidence_mode": cfg.rag.low_evidence_threshold < 0.5,
        # Protocol
        "pending_ttl_sec": cfg.protocol.pending_ttl_sec,
        "protocol_qa_ttl_sec": cfg.protocol.qa_ttl_sec,
        "active_protocol_ttl_sec": cfg.protocol.active_ttl_sec,
        "protocol_default_cooldown_sec": cfg.protocol.default_cooldown_sec,
        "protocol_generic_followup": cfg.protocol.generic_followup,
        # Rewrite
        "rewrite_protocol_enabled": cfg.rewrite.protocol_enabled,
        "rewrite_low_evidence_enabled": cfg.rewrite.low_evidence_enabled,
        "max_chars_protocol_main": cfg.rewrite.max_chars_protocol_main,
        "max_chars_protocol_followup": cfg.rewrite.max_chars_protocol_followup,
        "max_chars_normal": cfg.rewrite.max_chars_normal,
        "rewrite_enabled": cfg.rewrite.enabled,
        "rewrite_temperature": cfg.rewrite.temperature,
        "rewrite_top_p": cfg.rewrite.top_p,
        # TTS
        "tts_max_chars": cfg.speech.tts.max_chars,
        "tts_backend": cfg.speech.tts.backend,
        "tts_rate": cfg.speech.tts.rate,
        "tts_volume": cfg.speech.tts.volume,
        "tts_sapi_rate": cfg.speech.tts.sapi_rate,
        "tts_sapi_volume": cfg.speech.tts.sapi_volume,
        "tts_sherpa_model_dir": cfg.speech.tts.model_dir,
        "tts_sherpa_model_type": cfg.speech.tts.model_type,
        "tts_sherpa_threads": cfg.speech.tts.threads,
        "tts_sherpa_cache_size": cfg.speech.tts.cache_size,
        "tts_sherpa_speed": cfg.speech.tts.sherpa_speed,
        "tts_sherpa_sid": cfg.speech.tts.sherpa_sid,
        "tts_sherpa_noise_scale": cfg.speech.tts.sherpa_noise_scale,
        "tts_sherpa_noise_scale_w": cfg.speech.tts.sherpa_noise_scale_w,
        # LLM
        "llm_backend": "null" if cfg.llm.backend is None else cfg.llm.backend,
        "llm_ctx": cfg.llm.ctx,
        "llm_threads": cfg.llm.threads,
        "llm_gpu_layers": cfg.llm.gpu_layers,
        "llm_temperature": cfg.llm.temperature,
        "llm_stream": cfg.llm.stream,
        # Hardware
        "enable_led": cfg.hardware.enable_led,
        "enable_screen": cfg.hardware.enable_screen,
        "enable_precomputed_audio": cfg.hardware.enable_precomputed_audio,
        # Repeat
        "repeat_threshold": cfg.repeat.threshold,
        "variant_mode": cfg.repeat.variant_mode,
        # Debug
        "runtime_trace_enabled": cfg.debug.runtime_trace_enabled,
        "trace_path": cfg.debug.trace_path,
        "debug_runtime": cfg.debug.debug_runtime,
        "debug_tts": cfg.debug.debug_tts,
        "perf_warning_mb": cfg.hardware.perf_warning_mb,
    }


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


def load_runtime_config(profile: str | None = None) -> RuntimeConfig:
    """
    从统一配置体系加载运行时配置。

    每个字段都有合理的默认值，缺失配置不会报错。

    优先级（新体系）：
    1. 环境变量 / .env（向后兼容兜底）
    2. profiles/*.yaml（分层覆盖）
    3. profiles/base.yaml（全平台默认值）
    """
    # 1. 从新体系加载层级配置并扁平化
    settings = load_settings(profile=profile)
    values = _settings_to_flat(settings)

    # 2. 向后兼容：环境变量仍可覆盖（仅维护存量，不再扩展）
    for env_key, field_name in _ENV_FIELD_MAP.items():
        if env_key in os.environ and field_name in values:
            values[field_name] = _coerce_like(os.getenv(env_key), values[field_name])

    # 3. 标准化
    values["llm_backend"] = str(values["llm_backend"] or "auto").strip().lower()
    values["tts_backend"] = str(values["tts_backend"]).strip().lower()
    values["tts_sherpa_model_type"] = (
        str(values["tts_sherpa_model_type"]).strip().lower()
    )
    values["variant_mode"] = str(values["variant_mode"]).strip().lower()
    return RuntimeConfig(**values)
