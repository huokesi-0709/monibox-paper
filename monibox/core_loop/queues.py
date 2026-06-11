"""
Shared runtime queues.
"""

from __future__ import annotations

import queue

from monibox.core_loop.models import EngineEvent

input_queue: queue.Queue[EngineEvent] = queue.Queue(maxsize=100)
audio_in_queue: queue.Queue[EngineEvent] = queue.Queue(maxsize=100)
output_queue: queue.Queue[EngineEvent] = queue.Queue(maxsize=100)


def _drain_queue(q: queue.Queue[EngineEvent]) -> int:
    dropped = 0
    while True:
        try:
            q.get_nowait()
            dropped += 1
        except queue.Empty:
            return dropped


def clear_runtime_queues() -> dict[str, int]:
    return {
        "input": _drain_queue(input_queue),
        "audio_in": _drain_queue(audio_in_queue),
        "output": _drain_queue(output_queue),
    }
