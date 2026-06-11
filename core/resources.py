"""
core/resources.py

全局资源管理器：在系统启动时一次性加载庞大的模型避免重复载入。
涵盖：
1. ASR 引擎
2. TTS 引擎
3. LLM 后端
4. RAGEngine
"""

from __future__ import annotations

import os
from typing import Any

from language.backends import create_llm_backend
from runtime.runtime_config import load_runtime_config

# 延迟导入以防环境未装相关依赖
try:
    from speech.sherpa import SherpaTTS
except ImportError:
    SherpaTTS = None

try:
    from speech.whisper import (
        FasterWhisperASR as WhisperASR,
        WhisperASRConfig,
        build_default_initial_prompt,
    )
except ImportError:
    WhisperASR = None
    WhisperASRConfig = None
    build_default_initial_prompt = None


class ResourceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.rt = load_runtime_config()

        self.rag: Any | None = None
        self.llm: Any | None = None
        self.tts: Any | None = None
        self.asr: Any | None = None

        self._initialized = True

    def initialize_all(
        self,
        rag_db_path: str,
        enable_asr: bool = True,
        enable_tts: bool = True,
        preload_embedding: bool = True,
    ):
        """
        一次性加载所有需要的全局模型到内存/显存。
        针对 Windows 稳定性优化：
        1. 优先加载 ASR (Faster-Whisper)，它对 OpenMP 冲突最敏感。
        2. 给环境增加 PASSIVE 等待策略，减少多引擎竞争。
        """
        print("[Resource] 初始化核心引擎中...")

        # --- 稳定性环境补丁 ---
        os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
        os.environ["KMP_BLOCKTIME"] = "0"

        # 1. ASR (优先加载防止冲突)
        if enable_asr and WhisperASR is not None:
            print("[Resource] 加载 Faster-Whisper ASR 模型...")
            asr_model_dir = os.getenv(
                "WHISPER_MODEL_DIR", "models/asr/faster-whisper-small"
            )
            from app.config import resolve_project_path

            resolved_asr = resolve_project_path(asr_model_dir)
            try:
                # 修复：需要先构建 WhisperASRConfig
                asr_cfg = WhisperASRConfig(
                    model_dir=resolved_asr,
                    device=os.getenv("WHISPER_DEVICE", "cpu"),
                    compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                    language=os.getenv("WHISPER_LANGUAGE", "zh"),
                    initial_prompt=(
                        os.getenv("WHISPER_INITIAL_PROMPT")
                        or build_default_initial_prompt()
                    ),
                )
                self.asr = WhisperASR(asr_cfg)
                print("[Resource] ASR 加载成功。")
            except Exception as e:
                print(f"[Resource] [WARN] ASR 加载失败: {e}")
                self.asr = None

        # 2. RAG (Delay import to avoid Whisper OpenMP/CTranslate2 conflict)
        print("[Resource] 加载 RAG 引擎...")
        from runtime.rag_engine import RagEngine

        self.rag = RagEngine(rag_db_path)

        # 3. LLM
        print("[Resource] 加载 LLM 后端...")
        self.llm = create_llm_backend()

        # 4. Embedding（可选预加载）
        if preload_embedding:
            print("[Resource] 预加载 Embedding 模型...")
            try:
                from knowledgekit.embedder import get_model as get_embedding_model

                get_embedding_model()
            except Exception as e:
                print(f"[Resource] [WARN] Embedding 预加载跳过: {e}")

        # 5. TTS
        if enable_tts and self.rt.tts_backend == "sherpa" and SherpaTTS is not None:
            print("[Resource] 加载 Sherpa TTS 音色框架...")
            from app.config import resolve_project_path

            model_dir = resolve_project_path(self.rt.tts_sherpa_model_dir)
            self.tts = SherpaTTS(
                model_dir=model_dir,
                model_type=self.rt.tts_sherpa_model_type,
                num_threads=self.rt.tts_sherpa_threads,
                cache_size=self.rt.tts_sherpa_cache_size,
                speed=self.rt.tts_sherpa_speed,
                sid=self.rt.tts_sherpa_sid,
                noise_scale=self.rt.tts_sherpa_noise_scale,
                noise_scale_w=self.rt.tts_sherpa_noise_scale_w,
            )

        print("[Resource] [OK] 核心引擎初始化完成。")

    def get_rag(self):
        if not self.rag:
            raise RuntimeError("RAG Engine 未初始化！")
        return self.rag

    def get_llm(self) -> Any:
        if not self.llm:
            raise RuntimeError("LLM Backend 未初始化！")
        return self.llm

    def get_tts(self) -> Any | None:
        return self.tts

    def get_asr(self) -> Any | None:
        return self.asr


# 全局单例
global_resources = ResourceManager()
