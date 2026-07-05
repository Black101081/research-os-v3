import json
import unittest
from pathlib import Path

from bootstrap_ohlcv import warmup_engine
from paper_replay import run_paper_replay_demo
from realtime_engine import ResearchEngine


class IntegrationFlowTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).resolve().parent.parent / 'config.example.json').read_text())

    def test_paper_replay_generates_strategy_spec_and_packet(self):
        result = run_paper_replay_demo(self.config)
        self.assertGreaterEqual(len(result['strategy_specs']), 1)
        self.assertGreaterEqual(len(result['playbook_packets']), 1)
        self.assertEqual(result['strategy_specs'][0]['spec_version'], 'strategy_spec_v1')

    def test_warmup_then_replay_stack_is_consistent(self):
        engine = ResearchEngine(symbols=['BTC'], max_bars=500, thresholds=self.config['thresholds'])
        fake = []
        for i in range(60):
            price = 200 + i * 0.05
            fake.append({'t': 1783212600000 + i * 60000, 'T': 1783212659999 + i * 60000, 's': 'BTC', 'i': '1m', 'o': str(price - 0.1), 'c': str(price), 'h': str(price + 0.1), 'l': str(price - 0.2), 'v': str(10 + i)})
        from unittest.mock import patch
        with patch('bootstrap_ohlcv.fetch_candle_snapshot', return_value=fake):
            counts = warmup_engine(engine, ['BTC'], '1m', 60)
        snap = engine.snapshot()['BTC']
        self.assertEqual(counts['BTC'], 60)
        self.assertIn('MACD', snap['indicators'])
        self.assertIn('regime', snap['regime_state'])

if __name__ == '__main__':
    unittest.main()
