from __future__ import annotations

import unittest
import time
from telemetry import TelemetryTracker


class TestTelemetry(unittest.TestCase):
    def test_record_success(self):
        tracker = TelemetryTracker()
        tracker.record_success(0.005) # 5ms
        tracker.record_success(0.015) # 15ms
        
        metrics = tracker.get_metrics(active_candidates=2)
        self.assertEqual(metrics["total_messages"], 2)
        self.assertEqual(metrics["error_rate_pct"], 0.0)
        self.assertAlmostEqual(metrics["avg_latency_ms"], 10.0) # (5 + 15)/2 = 10ms
        self.assertEqual(metrics["active_candidates"], 2)

    def test_record_error(self):
        tracker = TelemetryTracker()
        tracker.record_error()
        
        metrics = tracker.get_metrics(active_candidates=0)
        self.assertEqual(metrics["total_messages"], 1)
        self.assertEqual(metrics["error_rate_pct"], 100.0)

    def test_msg_rate_calculation(self):
        tracker = TelemetryTracker()
        tracker.record_success(0.001)
        tracker.record_success(0.002)
        
        metrics = tracker.get_metrics()
        self.assertEqual(metrics["msg_rate_fps"], 0.2) # 2 messages in last 10s / 10s = 0.2

    def test_uptime_metric(self):
        tracker = TelemetryTracker()
        metrics = tracker.get_metrics()
        self.assertTrue(metrics["uptime_seconds"] >= 0)


if __name__ == "__main__":
    unittest.main()
