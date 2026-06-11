import gc
import os
import time

import psutil

from monibox.core_loop.trace_logger import get_runtime_trace_logger


class PerfMonitor:
    """性能与内存监控器：用于边缘设备上的长时间运行防护"""

    def __init__(self, warning_mb: int = 512):
        self.warning_mb = warning_mb
        self.process = psutil.Process(os.getpid())
        self.timers = {}
        self._trace = get_runtime_trace_logger()

    def start_timer(self, name: str):
        self.timers[name] = time.perf_counter()

    def end_timer(self, name: str) -> float:
        if name in self.timers:
            elapsed = time.perf_counter() - self.timers.pop(name)
            return elapsed
        return 0.0

    def check_memory(self, interaction_id: str | None = None):
        """检查当前内存水位，超出阈值则报警并强制 GC"""
        mem_info = self.process.memory_info()
        rss_mb = mem_info.rss / 1024 / 1024
        self._trace.log(
            "memory_sample",
            interaction_id=interaction_id,
            rss_mb=round(rss_mb, 1),
            warning_mb=self.warning_mb,
        )

        if rss_mb > self.warning_mb:
            print(
                f"[PerfMonitor] WARNING: Memory usage {rss_mb:.1f} MB exceeds {self.warning_mb} MB! Triggering GC..."
            )
            self._trace.log(
                "memory_warning",
                interaction_id=interaction_id,
                rss_mb=round(rss_mb, 1),
                warning_mb=self.warning_mb,
            )
            gc.collect()

            # 再次检查
            mem_info_after = self.process.memory_info()
            rss_mb_after = mem_info_after.rss / 1024 / 1024
            print(
                f"[PerfMonitor] After GC: {rss_mb_after:.1f} MB (Recovered: {rss_mb - rss_mb_after:.1f} MB)"
            )
            self._trace.log(
                "memory_gc",
                interaction_id=interaction_id,
                rss_mb_after=round(rss_mb_after, 1),
                recovered_mb=round(rss_mb - rss_mb_after, 1),
            )

        return rss_mb
