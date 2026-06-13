"""
webui/adapters/web_tts.py

TTS 适配器：将合成音频保存为 WAV 文件，供 Streamlit 播放。
不改动现有 TTS 引擎，直接复用 sherpa-onnx 底层 API。
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path

# 项目根目录注入（供 Streamlit 直接运行）
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from app.config import resolve_project_path
from app.settings import get_settings

logger = logging.getLogger(__name__)


class WebTTS:
    """
    为 WebUI 提供的 TTS 适配器。

    - 优先使用 sherpa-onnx（可获取原始音频数据）
    - 合成后保存为临时 WAV 文件，返回文件路径
    - 如果 sherpa-onnx 不可用，则降级为仅文本输出（返回 None）
    """

    def __init__(self) -> None:
        self._tts_engine = None
        self._model_type: str = "melo"
        self._sample_rate: int = 22050
        self._init()

    def _init(self) -> None:
        """尝试加载 sherpa-onnx TTS 引擎。"""
        try:
            import sherpa_onnx
        except ImportError:
            logger.warning("sherpa-onnx 未安装，WebTTS 将不可用（仅文本输出）")
            return

        cfg = get_settings().speech.tts
        if cfg.backend != "sherpa":
            logger.info("当前 TTS 后端为 %s，WebTTS 优先尝试加载 sherpa", cfg.backend)

        model_dir = Path(resolve_project_path(cfg.model_dir))
        if not model_dir.exists():
            logger.warning("TTS 模型目录不存在: %s", model_dir)
            return

        # 绕过中文路径 bug
        model_dir_str = str(model_dir)
        if not model_dir_str.isascii():
            cache_dir = Path.home() / ".cache" / "monibox_tts" / model_dir.name
            if not cache_dir.exists():
                cache_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(model_dir, cache_dir)
            model_dir = cache_dir

        model_path = model_dir / "model.onnx"
        tokens_path = model_dir / "tokens.txt"
        if not model_path.exists() or not tokens_path.exists():
            logger.warning("TTS 模型文件不完整: %s", model_dir)
            return

        self._model_type = cfg.model_type.strip().lower()

        try:
            if self._model_type == "melo":
                lexicon_path = model_dir / "lexicon.txt"
                dict_dir = model_dir / "dict"
                rule_fsts = []
                for fst_name in ["date.fst", "number.fst", "phone.fst"]:
                    fst_path = model_dir / fst_name
                    if fst_path.exists():
                        rule_fsts.append(str(fst_path))

                tts_config = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                            model=str(model_path),
                            lexicon=str(lexicon_path) if lexicon_path.exists() else "",
                            tokens=str(tokens_path),
                            dict_dir=str(dict_dir) if dict_dir.exists() else "",
                        ),
                        num_threads=cfg.threads,
                        debug=False,
                    ),
                    rule_fsts=",".join(rule_fsts) if rule_fsts else "",
                )
            else:
                data_dir = model_dir / "espeak-ng-data"
                tts_config = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                            model=str(model_path),
                            tokens=str(tokens_path),
                            data_dir=str(data_dir) if data_dir.exists() else "",
                        ),
                        num_threads=cfg.threads,
                        debug=False,
                    )
                )

            self._tts_engine = sherpa_onnx.OfflineTts(tts_config)
            logger.info("WebTTS 引擎加载成功: %s", model_dir)
        except Exception as e:
            logger.error("WebTTS 引擎加载失败: %s", e)

    @property
    def available(self) -> bool:
        return self._tts_engine is not None

    def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        sid: int = 0,
    ) -> Path | None:
        """
        合成文本为 WAV 文件。

        Returns:
            临时 WAV 文件路径，若引擎不可用则返回 None。
        """
        if not self.available:
            return None

        t = (text or "").strip()
        if not t:
            return None

        try:
            audio = self._tts_engine.generate(t, sid=sid, speed=speed)
            if not audio.samples:
                logger.warning("TTS 合成返回空音频: %s", t[:30])
                return None

            samples = np.array(audio.samples, dtype=np.float32)
            sample_rate = audio.sample_rate

            # 保存为临时 WAV
            fd, path = tempfile.mkstemp(suffix=".wav")
            Path(path).write_bytes(self._to_wav_bytes(samples, sample_rate))
            return Path(path)
        except Exception as e:
            logger.error("TTS 合成失败: %s", e)
            return None

    @staticmethod
    def _to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
        """将 float32 样本写入标准 WAV 格式字节。"""
        from scipy.io import wavfile

        # float32 -> int16
        samples_int16 = (samples * 32767).astype(np.int16)
        fd, path = tempfile.mkstemp(suffix=".wav")
        try:
            wavfile.write(path, sample_rate, samples_int16)
            data = Path(path).read_bytes()
        finally:
            Path(path).unlink(missing_ok=True)
        return data
