import unittest
from fastapi.testclient import TestClient
import app


class ApiSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)

    def test_health_endpoint(self):
        r = self.client.get('/api/health')
        self.assertEqual(r.status_code, 200)
        self.assertIn('status', r.json())

    def test_config_endpoint(self):
        r = self.client.get('/api/config')
        self.assertEqual(r.status_code, 200)
        self.assertIn('symbols', r.json())

    def test_snapshot_endpoint(self):
        r = self.client.get('/api/snapshot')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), dict)

    def test_validation_and_specs_endpoints(self):
        rv = self.client.get('/api/validation')
        rs = self.client.get('/api/specs')
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rs.status_code, 200)
        self.assertIn('strategy_specs', rs.json())
        self.assertIn('playbook_packets', rs.json())


if __name__ == '__main__':
    unittest.main()
