from __future__ import annotations

import unittest
import uuid
from fastapi.testclient import TestClient
from app import app


class TestLiveGatingRoute(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_toggle_trading_mode(self):
        # Initial call to get current mode
        telemetry = self.client.get("/api/telemetry").json()
        initial_mode = telemetry["trading_mode"]
        
        # 1. Verify toggle fails without confirm
        response_bad = self.client.post("/api/toggle-trading-mode", json={})
        self.assertEqual(response_bad.status_code, 400)
        self.assertIn("requires explicit confirmation", response_bad.json()["detail"])
        
        # 2. Toggle mode with correct confirm
        response = self.client.post("/api/toggle-trading-mode", json={"confirm": "TOGGLE"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        new_mode = data["trading_mode"]
        
        # Verify it toggled
        self.assertNotEqual(initial_mode, new_mode)
        
        # Check telemetry reflects the update
        telemetry_after = self.client.get("/api/telemetry").json()
        self.assertEqual(telemetry_after["trading_mode"], new_mode)

    def test_kill_switch_and_reset(self):
        # 1. Check that triggering Kill Switch without confirmation fails with 400
        response_bad = self.client.post("/api/kill-switch", json={})
        self.assertEqual(response_bad.status_code, 400)
        self.assertIn("requires explicit confirmation", response_bad.json()["detail"])

        # 2. Trigger Kill Switch with correct confirmation
        token = f"test_token_{uuid.uuid4()}"
        response = self.client.post(
            "/api/kill-switch", 
            json={"confirm": "CONFIRM", "idempotency_token": token}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["kill_switch_active"])
        
        # 3. Test idempotency with duplicate request
        response_dup = self.client.post(
            "/api/kill-switch", 
            json={"confirm": "CONFIRM", "idempotency_token": token}
        )
        self.assertEqual(response_dup.status_code, 200)
        self.assertEqual(response_dup.json()["message"], "Duplicate request processed via idempotency token.")
        
        # Verify telemetry reflects kill switch is active
        telemetry = self.client.get("/api/telemetry").json()
        self.assertTrue(telemetry["kill_switch_active"])

        # 4. Check resetting without confirmation fails with 400
        response_reset_bad = self.client.post("/api/kill-switch/reset", json={})
        self.assertEqual(response_reset_bad.status_code, 400)
        self.assertIn("requires explicit confirmation", response_reset_bad.json()["detail"])

        # 5. Reset Kill Switch with correct confirmation
        response_reset = self.client.post("/api/kill-switch/reset", json={"confirm": "RESET"})
        self.assertEqual(response_reset.status_code, 200)
        data_reset = response_reset.json()
        self.assertEqual(data_reset["status"], "success")
        self.assertFalse(data_reset["kill_switch_active"])

        # Verify telemetry reflects kill switch is inactive
        telemetry_after = self.client.get("/api/telemetry").json()
        self.assertFalse(telemetry_after["kill_switch_active"])


if __name__ == "__main__":
    unittest.main()
