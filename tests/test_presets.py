from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from app import app


class TestPresetsRoute(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_presets(self):
        response = self.client.get("/api/presets")
        self.assertEqual(response.status_code, 200)
        presets = response.json()
        self.assertIsInstance(presets, list)
        self.assertGreater(len(presets), 0)
        
        # Verify first preset has required keys
        first = presets[0]
        self.assertIn("name", first)
        self.assertIn("description", first)
        self.assertIn("category", first)
        self.assertIn("spec", first)
        self.assertIn("strategy_family", first["spec"])


if __name__ == "__main__":
    unittest.main()
