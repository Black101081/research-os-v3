from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from app import app


class TestLiveGatingRoute(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_toggle_trading_mode(self):
        # Initial call to get current mode
        telemetry = self.client.get("/api/telemetry").json()
        initial_mode = telemetry["trading_mode"]
        
        # Toggle mode
        response = self.client.post("/api/toggle-trading-mode")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        new_mode = data["trading_mode"]
        
        # Verify it toggled
        self.assertNotEqual(initial_mode, new_mode)
        
        # Check telemetry reflects the update
        telemetry_after = self.client.get("/api/telemetry").json()
        self.assertEqual(telemetry_after["trading_mode"], new_mode)

    def test_kill_switch(self):
        # Trigger Kill Switch
        response = self.client.post("/api/kill-switch")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["kill_switch_active"])
        
        # Verify telemetry reflects kill switch is active
        telemetry = self.client.get("/api/telemetry").json()
        self.assertTrue(telemetry["kill_switch_active"])


if __name__ == "__main__":
    unittest.main()
