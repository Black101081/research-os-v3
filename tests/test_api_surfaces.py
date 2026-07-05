import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

import app as app_module


class ApiSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app_module.app)

    def test_research_validator_endpoint_returns_summary(self):
        resp = self.client.get('/api/research-validator')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)
        self.assertIn('factor_count', data['summary'])
        self.assertIn('signal_count', data['summary'])
        self.assertIn('strategy_family_count', data['summary'])

    def test_backtest_bridge_demo_endpoint_returns_jobs(self):
        resp = self.client.get('/api/backtest-bridge-demo')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('job_count', data)
        self.assertGreaterEqual(data['job_count'], 1)
        self.assertIn('jobs', data)
        self.assertIn('decision_gate', data['jobs'][0])

    def test_backtest_runner_demo_endpoint_returns_results(self):
        resp = self.client.get('/api/backtest-runner-demo')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('result_count', data)
        self.assertGreaterEqual(data['result_count'], 1)
        self.assertIn('results', data)
        self.assertIn('runner_metrics', data['results'][0])
        self.assertIn('decision_gate', data['results'][0])


if __name__ == '__main__':
    unittest.main()
