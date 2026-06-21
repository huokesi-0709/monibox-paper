"""
app/settings.py

MoniBox 统一配置加载器（重构后）
--------------------------------
将原本散落在 .env、profiles/*.yaml、runtime_config.py 及代码各处的配置
统一收敛到本模块，提供：

1. 分层加载：base.yaml → {platform}.yaml → .env（仅注入机密）
2. 递归 merge：override 覆盖 base，支持嵌套层级
3. Pydantic 校验：启动时报错，防止配置错误流入运行时
4. 向后兼容：runtime_config.py 仍可作为 facade 调用本模块

加载优先级（从低到高）：
    profiles/base.yaml          — 全平台默认值
    profiles/{platform}.yaml    — 平台差异覆盖（递归 merge）
    .env                        — 仅注入 API Key 等机密（通过 Pydantic Settings）

用法：
    from app.settings import get_settings
    cfg = get_settings()
    print(cfg.speech.tts.backend)
    print(cfg.llm.ctx)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import PROJECT_ROOT

ALLOW_PAPER_ENV_OVERRIDE_ENV = "ALLOW_PAPER_ENV_OVERRIDE"


# ============================================================================
# 子系统配置模型
# ============================================================================

class AppConfig(BaseModel):
    log_level: str = "INFO"
    mode: str = "text"


class LlmConfig(BaseModel):
    backend: str | None = "auto"
    timeout: int = 30
    max_retries: int = 3
    ctx: int = 2048
    threads: int = 6
    gpu_layers: int = 0
    chat_format: str = "chatml"
    temperature: float = 0.3
    stream: bool = False
    gguf_path: str | None = None


class RagConfig(BaseModel):
    top_k: int = 5
    max_distance: float = 0.42
    low_evidence_threshold: float = 0.3
    db_path: str = "build/rag.db"
    runtime_pack_path: str = "build/runtime_pack.json"


class ProtocolConfig(BaseModel):
    pending_ttl_sec: float = 15.0
    qa_ttl_sec: float = 25.0
    active_ttl_sec: float = 45.0
    default_cooldown_sec: float = 20.0
    generic_followup: str = (
        "我在。你现在情况有没有变化？有出血或呼吸困难马上告诉我。"
    )


class RewriteConfig(BaseModel):
    enabled: bool = True
    protocol_enabled: bool = True
    low_evidence_enabled: bool = True
    max_chars_protocol_main: int = 78
    max_chars_protocol_followup: int = 65
    max_chars_normal: int = 90
    temperature: float = 0.2
    top_p: float = 0.9


class AsrConfig(BaseModel):
    model_path: str = "models/asr/faster-whisper-small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "zh"
    initial_prompt: str | None = None
    corrections_json: str = ""


class TtsConfig(BaseModel):
    backend: str = "sherpa"
    max_chars: int = 90
    model_dir: str = "models/tts/sherpa/vits-icefall-zh-aishell3"
    model_type: str = "melo"
    threads: int = 4
    cache_size: int = 100
    sherpa_sid: int = 173
    sherpa_speed: float = 0.92
    sherpa_noise_scale: float = 0.72
    sherpa_noise_scale_w: float = 0.85
    # 兼容参数
    rate: int = 180
    volume: float = 1.0
    sapi_rate: int = 0
    sapi_volume: int = 100
    poll_ms: int = 200
    max_play_sec: float = 25.0


class VadConfig(BaseModel):
    sample_rate: int = 16000
    start_rms: float = 0.006
    end_rms: float = 0.0065
    min_record_ms: int = 500
    end_sil_ms: int = 800
    max_sec: int = 12
    pre_roll_ms: int = 400


class AsrTimingConfig(BaseModel):
    arm_delay_sec: float = 1.5
    post_arm_guard_sec: float = 2.0


class SpeechConfig(BaseModel):
    asr: AsrConfig = Field(default_factory=AsrConfig)
    tts: TtsConfig = Field(default_factory=TtsConfig)
    vad: VadConfig = Field(default_factory=VadConfig)
    asr_timing: AsrTimingConfig = Field(default_factory=AsrTimingConfig)


class BuildConfig(BaseModel):
    embedding_model: str = "models/embedding/bge-small-zh-v1.5"
    chunk_max_chars: int = 60
    chunk_min_chars: int = 15


class DebugConfig(BaseModel):
    runtime_trace_enabled: bool = True
    trace_path: str = "build/runtime_logs/interaction_trace.jsonl"
    debug_runtime: bool = False
    debug_tts: bool = False


class HardwareConfig(BaseModel):
    enable_led: bool = True
    enable_screen: bool = True
    enable_precomputed_audio: bool = False
    perf_warning_mb: int = 600


class RepeatConfig(BaseModel):
    threshold: float = 0.92
    variant_mode: str = "rr"


# ============================================================================
# 顶层配置模型（合并 .env 机密）
# ============================================================================

class MoniboxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    rag: RagConfig = Field(default_factory=RagConfig)
    protocol: ProtocolConfig = Field(default_factory=ProtocolConfig)
    rewrite: RewriteConfig = Field(default_factory=RewriteConfig)
    speech: SpeechConfig = Field(default_factory=SpeechConfig)
    build: BuildConfig = Field(default_factory=BuildConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    repeat: RepeatConfig = Field(default_factory=RepeatConfig)

    # 构建侧：从 .env 注入的机密/高频覆盖
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_chat: str = "deepseek-chat"
    deepseek_model_reasoner: str = "deepseek-reasoner"

    @field_validator("deepseek_api_key", mode="before")
    @classmethod
    def _strip_api_key(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


# ============================================================================
# 加载逻辑
# ============================================================================

def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并两个字典，override 覆盖 base 的同名键。"""
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """安全加载 YAML 文件，失败返回空字典。"""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _apply_env_overrides(config_data: dict[str, Any]) -> dict[str, Any]:
    """
    手动应用环境变量覆盖（__ 分隔符表示嵌套层级）。

    pydantic-settings 中 init kwargs 优先级高于 env vars，
    因此我们需要在传入 MoniboxSettings 之前手动把 env var 合并进 config_data。
    """
    for key, raw_value in os.environ.items():
        if "__" not in key:
            continue
        parts = key.lower().split("__")
        target = config_data
        # 逐层导航，若中间层级缺失则跳过
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                break
            target = target[part]
        else:
            leaf = parts[-1]
            if leaf not in target:
                continue
            original = target[leaf]
            # 尽量保持原类型
            if isinstance(original, bool):
                val = str(raw_value).strip().lower() in {"1", "true", "yes", "on"}
            elif isinstance(original, int) and not isinstance(original, bool):
                try:
                    val = int(raw_value)
                except ValueError:
                    val = raw_value
            elif isinstance(original, float):
                try:
                    val = float(raw_value)
                except ValueError:
                    val = raw_value
            else:
                val = raw_value
            target[leaf] = val
    return config_data


def _allow_paper_env_override() -> bool:
    return os.getenv(ALLOW_PAPER_ENV_OVERRIDE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def load_settings(
    profile: str | None = None,
    profiles_dir: str | Path = "profiles",
) -> MoniboxSettings:
    """
    加载完整配置。

    参数:
        profile: 平台名称，如 "windows", "radxa_extreme"。
                 默认从 RUNTIME_PROFILE 环境变量读取。
        profiles_dir: profiles 目录路径，相对项目根目录或绝对路径。
    """
    profiles_dir_path = (
        PROJECT_ROOT / profiles_dir
        if not Path(profiles_dir).is_absolute()
        else Path(profiles_dir)
    )

    # 1. 加载 base.yaml
    config_data = _load_yaml(profiles_dir_path / "base.yaml")

    # 2. 加载平台差异文件并递归 merge
    profile_name = (
        profile or os.getenv("RUNTIME_PROFILE", "") or ""
    ).strip()
    if profile_name and profile_name.lower() not in {"none", "off", "0", ""}:
        profile_path = profiles_dir_path / f"{profile_name}.yaml"
        override = _load_yaml(profile_path)
        if override:
            config_data = _deep_merge(config_data, override)

    # 3. 环境变量覆盖（__ 分隔符，如 SPEECH__TTS__BACKEND=pyttsx3）。
    # paper_eval 默认锁定，避免本地 demo/API/voice/hardware 环境变量污染论文复现实验；
    # 如确需调试，可显式设置 ALLOW_PAPER_ENV_OVERRIDE=1。
    if profile_name != "paper_eval" or _allow_paper_env_override():
        config_data = _apply_env_overrides(config_data)

    # 4. Pydantic 校验 + .env 机密注入
    return MoniboxSettings(**config_data)


# ============================================================================
# 全局单例（惰性加载）
# ============================================================================

_settings_instance: MoniboxSettings | None = None


def get_settings() -> MoniboxSettings:
    """获取全局配置单例（惰性加载）。"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = load_settings()
    return _settings_instance


def reload_settings() -> MoniboxSettings:
    """强制重新加载配置（调试用）。"""
    global _settings_instance
    _settings_instance = load_settings()
    return _settings_instance
