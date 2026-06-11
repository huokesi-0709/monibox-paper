"""
monibox/core_loop/models.py

定义贯穿系统的核心消息类型和枚举
"""

import enum
from dataclasses import dataclass, field
from typing import Any


class EventType(enum.Enum):
    AUDIO_IN = "audio_in"  # 来自麦克风的 PCM 数据
    TEXT_IN = "text_in"  # 文本输入（如 ASR 结果，或单纯文本测试）
    TTS_CHUNK = "tts_chunk"  # 生成好的 TTS 音频切片，待播放
    AUDIO_OUT = "audio_out"  # 特殊音频播放指令（比如播放警报声的 wav 文件）
    SENSOR_IMU = "sensor_imu"  # IMU 传感器事件 (强震动, 跌落等)
    SYS_CTRL = "sys_ctrl"  # 系统控制事件 (退出, 暂停等)


@dataclass
class EngineEvent:
    """
    流转于主总线的三大队列中的封装事件
    """

    event_type: EventType
    data: Any
    metadata: dict[str, Any] = field(default_factory=dict)
