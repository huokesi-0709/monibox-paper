"""
monibox/audio/vad_recorder.py

用途
-----
VAD(简易能量阈值) 自动录音（支持 pre-roll）：
- 持续监听麦克风
- 检测到开始说话后，把“开始前的 200~400ms”也拼进去（pre-roll）
  避免切掉句首造成 ASR 误识别
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class VadConfig:
    sample_rate: int = 16000
    block_ms: int = 30
    start_rms: float = 0.012
    end_rms: float | None = None
    min_speech_ms: int = 150  # 缩短开始所需的连续语音长度，更快拾音
    min_record_ms: int = 500
    end_silence_ms: int = 800
    max_seconds: float = 12.0
    pre_roll_ms: int = 400  # 放宽 pre-roll，彻底防斩头
    device: int | None = None


def _rms(x: np.ndarray) -> float:
    x = x.astype(np.float32)
    return float(np.sqrt(np.mean(x * x) + 1e-12))


def _resolve_end_rms(cfg: VadConfig, noise_floor: float) -> float:
    if cfg.end_rms is not None:
        return float(cfg.end_rms)

    adaptive = max(cfg.start_rms * 0.9, noise_floor + 0.0015)
    return min(cfg.start_rms * 1.2, adaptive)


def record_vad(cfg: VadConfig) -> np.ndarray | None:
    sr = int(cfg.sample_rate)
    block_size = int(sr * cfg.block_ms / 1000)

    need_start_blocks = max(1, int(cfg.min_speech_ms / cfg.block_ms))
    min_record_blocks = max(1, int(cfg.min_record_ms / cfg.block_ms))
    end_sil_blocks = max(1, int(cfg.end_silence_ms / cfg.block_ms))
    max_blocks = int(cfg.max_seconds * 1000 / cfg.block_ms)

    pre_roll_blocks = max(0, int(cfg.pre_roll_ms / cfg.block_ms))
    pre_buf = deque(maxlen=pre_roll_blocks)

    chunks = []
    started = False
    start_hits = 0
    silence_hits = 0
    smoothed_level = 0.0
    noise_floor = 0.0

    with sd.InputStream(
        samplerate=sr,
        channels=1,
        dtype="float32",
        blocksize=block_size,
        device=cfg.device,
    ) as stream:
        for _ in range(max_blocks):
            data, overflowed = stream.read(block_size)
            x = data.reshape(-1)
            raw_level = _rms(x)

            # EMA 平滑，抵抗极短促的脉冲敲击噪声
            smoothed_level = (
                0.4 * smoothed_level + 0.6 * raw_level
                if smoothed_level > 0
                else raw_level
            )

            # 调试输出：每 10 个数据块输出一次当前音量，方便用户调节 VAD_START_RMS
            if os.getenv("DEBUG_RUNTIME") == "1" and _ % 20 == 0:
                # 使用 ANSI 转义控制字符打印在同一行
                print(
                    f"\r[VAD] RMS: {smoothed_level:.4f} (Threshold: {cfg.start_rms:.4f})  ",
                    end="",
                    flush=True,
                )

            # 永远维护 pre-roll 缓冲
            if pre_roll_blocks > 0:
                pre_buf.append(x.copy())

            if not started:
                if raw_level < cfg.start_rms:
                    noise_floor = (
                        raw_level
                        if noise_floor <= 0
                        else (0.8 * noise_floor + 0.2 * raw_level)
                    )

                # 使用平滑后的 level 判断
                if smoothed_level >= cfg.start_rms:
                    start_hits += 1
                else:
                    # 允许 1 个 block 的掉线容错，不立刻归零
                    start_hits = max(0, start_hits - 2)

                if start_hits >= need_start_blocks:
                    started = True
                    # 把 pre-roll 拼进来（关键）
                    if pre_roll_blocks > 0 and len(pre_buf) > 0:
                        chunks.extend(list(pre_buf))
                    chunks.append(x.copy())
                    silence_hits = 0
                continue

            # started == True
            chunks.append(x.copy())

            end_rms = _resolve_end_rms(cfg, noise_floor)
            if os.getenv("DEBUG_RUNTIME") == "1" and len(chunks) % 20 == 0:
                print(
                    f"\r[VAD] RMS: {smoothed_level:.4f} (Start: {cfg.start_rms:.4f}, End: {end_rms:.4f})  ",
                    end="",
                    flush=True,
                )

            # 结束判定改用 raw_level，避免 EMA 回落过慢导致总是拖到 max_seconds
            if raw_level < end_rms:
                silence_hits += 1
            else:
                silence_hits = 0

            if len(chunks) >= min_record_blocks and silence_hits >= end_sil_blocks:
                break

    if not started or not chunks:
        return None

    audio = np.concatenate(chunks, axis=0).astype(np.float32)
    if audio.shape[0] < int(sr * 0.25):
        return None
    return audio
