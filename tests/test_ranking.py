from __future__ import annotations

import unittest
from fastapi.testclient import TestClient
from app import app


class TestRankingRoute(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_ranking_endpoint(self):
        response = self.client.get("/api/ranking")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check overall schema
        self.assertIn("ranked_strategies", data)
        self.assertIn("rules", data)
        self.assertIn("promote_threshold", data["rules"])
        self.assertIn("metrics_weights", data["rules"])
        
        # Check details of ranked strategies
        ranked = data["ranked_strategies"]
        if len(ranked) > 0:
            first = ranked[0]
            self.assertIn("symbol", first)
            self.assertIn("strategy_name", first)
            self.assertIn("composite_score", first)
            self.assertIn("perf_score", first)
            self.assertIn("decision", first)
            self.assertIn("rank", first)
            
            # Verify they are ordered in descending composite_score
            scores = [x["composite_score"] for x in ranked]
            self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    import unittest
    unittest.main()
