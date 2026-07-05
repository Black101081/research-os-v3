from __future__ import annotations

import unittest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app import app


class TestPlaybookExportRoute(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.symbol = "BTC"
        self.strategy_name = "macd_trend_continuation"

    def test_post_export_playbook(self):
        # We can pass empty dictionary to test fallback logic
        response = self.client.post(
            f"/api/export-playbook/{self.symbol}/{self.strategy_name}",
            json={}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("file_path", data)
        self.assertIn("spec_path", data)
        self.assertIn("code", data)
        self.assertIn("class MacdTrendContinuationPlaybook:", data["code"])
        
        # Verify the actual files got exported to disk
        py_file = Path(data["file_path"])
        json_file = Path(data["spec_path"])
        self.assertTrue(py_file.exists())
        self.assertTrue(json_file.exists())
        
        saved_spec = json.loads(json_file.read_text())
        self.assertEqual(saved_spec["symbol"], self.symbol)
        self.assertEqual(saved_spec["strategy_family"], self.strategy_name)


if __name__ == "__main__":
    unittest.main()
