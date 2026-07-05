from __future__ import annotations

import unittest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app import app


class TestBriefFeedbackRoute(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.symbol = "BTC"
        self.strategy_name = "bollinger_squeeze_breakout"

    def test_get_research_brief(self):
        response = self.client.get(f"/api/research-brief/{self.symbol}/{self.strategy_name}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("symbol", data)
        self.assertIn("strategy_name", data)
        self.assertIn("brief_md", data)
        self.assertTrue(data["brief_md"].startswith("# Research Brief:"))

    def test_post_research_brief_feedback(self):
        payload = {
            "comments": "Test override to promote this strategy spec.",
            "decision": "AUTO_PROMOTE"
        }
        response = self.client.post(
            f"/api/research-brief/{self.symbol}/{self.strategy_name}/feedback",
            json=payload
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["decision"], "AUTO_PROMOTE")
        self.assertEqual(data["lane"], "promote")
        
        # Verify JSON file got created
        path = Path(f"data/research_briefs/{self.symbol}_{self.strategy_name}_feedback.json")
        self.assertTrue(path.exists())
        saved = json.loads(path.read_text())
        self.assertEqual(saved["comments"], payload["comments"])
        self.assertEqual(saved["decision"], payload["decision"])


if __name__ == "__main__":
    unittest.main()
