from __future__ import annotations

import time
from collections import deque
from typing import Dict, Any


class TelemetryTracker:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.total_messages = 0
        self.total_errors = 0
        self.latencies: deque[float] = deque(maxlen=100)  # last 100 processing times in ms
        self.message_times: deque[float] = deque()  # timestamps of processed messages in last 10s

    def record_success(self, duration_sec: float) -> None:
        self.total_messages += 1
        self.latencies.append(duration_sec * 1000.0)
        self.message_times.append(time.time())
        self._prune_message_times()

    def record_error(self) -> None:
        self.total_messages += 1
        self.total_errors += 1
        self.message_times.append(time.time())
        self._prune_message_times()

    def _prune_message_times(self) -> None:
        now = time.time()
        while self.message_times and now - self.message_times[0] > 10.0:
            self.message_times.popleft()

    def get_metrics(self, active_candidates: int = 0) -> Dict[str, Any]:
        now = time.time()
        uptime = now - self.start_time
        
        self._prune_message_times()
        msg_rate = len(self.message_times) / 10.0
        
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0.0
        error_rate = (self.total_errors / self.total_messages) * 100.0 if self.total_messages else 0.0
        
        return {
            "uptime_seconds": int(uptime),
            "total_messages": self.total_messages,
            "error_rate_pct": error_rate,
            "avg_latency_ms": avg_latency,
            "msg_rate_fps": msg_rate,
            "active_candidates": active_candidates
        }
