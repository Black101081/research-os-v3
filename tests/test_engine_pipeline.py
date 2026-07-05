import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from realtime_engine import ResearchEngine
from strategy_spec_builder import build_strategy_spec_v1
from playbook_bridge import build_playbook_packet
from registry_writer import RegistryWriter
from bootstrap_ohlcv import warmup_engine


class EnginePipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).resolve().parent.parent / 'config.example.json').read_text())
        self.thresholds = self.config['thresholds']

    def _build_engine(self):
        return ResearchEngine(symbols=['BTC'], max_bars=500, thresholds=self.thresholds)

    def test_live_candle_schema_replaces_same_bar(self):
        engine = self._build_engine()
        msg1 = {'channel': 'candle', 'data': {'t': 1783212600000, 'T': 1783212659999, 's': 'BTC', 'i': '1m', 'o': '63041.0', 'c': '63048.0', 'h': '63049.0', 'l': '63041.0', 'v': '0.14133', 'n': 28}}
        msg2 = {'channel': 'candle', 'data': {'t': 1783212600000, 'T': 1783212659999, 's': 'BTC', 'i': '1m', 'o': '63041.0', 'c': '63049.0', 'h': '63049.0', 'l': '63041.0', 'v': '0.81495', 'n': 36}}
        engine.process_message(msg1)
        engine.process_message(msg2)
        snap = engine.snapshot()['BTC']
        self.assertEqual(len(snap['bars']), 1)
        self.assertEqual(snap['bars'][-1]['close'], 63049.0)
        self.assertEqual(snap['bars'][-1]['volume'], 0.81495)

    def test_trade_bbo_and_mid_updates_state(self):
        engine = self._build_engine()
        engine.process_message({'channel': 'trades', 'data': [{'coin': 'BTC', 'px': '63019.0'}]})
        engine.process_message({'channel': 'bbo', 'data': {'coin': 'BTC', 'bid': '63019.0', 'ask': '63020.0'}})
        engine.process_message({'channel': 'allMids', 'data': {'BTC': '63019.5'}})
        snap = engine.snapshot()['BTC']
        self.assertEqual(snap['last_trade'], 63019.0)
        self.assertEqual(snap['bid'], 63019.0)
        self.assertEqual(snap['ask'], 63020.0)
        self.assertEqual(snap['mid'], 63019.5)

    def test_full_pipeline_generates_strategy_spec_when_signal_active(self):
        engine = self._build_engine()
        for i in range(60):
            base = 100 + i * 0.18 + math.sin(i / 8) * 0.03
            engine.process_message({'channel': 'candle', 'data': {'coin': 'BTC', 't': f'2026-07-05T01:{i:02d}:00Z', 'o': base - 0.05, 'h': base + 0.08, 'l': base - 0.08, 'c': base, 'v': 1000 + i * 2}})
        engine.process_message({'channel': 'trades', 'data': [{'coin': 'BTC', 'px': 110.81}]})
        snap = engine.snapshot()['BTC']
        self.assertIn('MACD', snap['indicators'])
        self.assertEqual(snap['regime_state']['regime'], 'uptrend')
        self.assertTrue(snap['signals']['macd_trend_continuation']['active'])
        self.assertTrue(snap['strategies']['macd_trend_continuation']['execution_ready'])
        spec = build_strategy_spec_v1('BTC', 'macd_trend_continuation', snap['signals']['macd_trend_continuation'], snap, self.config)
        packet = build_playbook_packet(spec)
        self.assertEqual(spec['spec_version'], 'strategy_spec_v1')
        self.assertEqual(packet['current_stage'], 'intake_and_hypothesis')
        self.assertEqual(packet['strategy_spec']['spec_id'], spec['spec_id'])

    def test_warmup_bootstrap_loads_history_with_mocked_snapshot(self):
        engine = self._build_engine()
        fake = []
        for i in range(50):
            price = 200 + i * 0.1
            fake.append({'t': 1783212600000 + i * 60000, 'T': 1783212659999 + i * 60000, 's': 'BTC', 'i': '1m', 'o': str(price - 0.1), 'c': str(price), 'h': str(price + 0.1), 'l': str(price - 0.2), 'v': str(10 + i)})
        with patch('bootstrap_ohlcv.fetch_candle_snapshot', return_value=fake):
            counts = warmup_engine(engine, ['BTC'], '1m', 50)
        snap = engine.snapshot()['BTC']
        self.assertEqual(counts['BTC'], 50)
        self.assertEqual(len(snap['bars']), 50)
        self.assertIn('MACD', snap['indicators'])

    def test_registry_writes_snapshot_specs_and_packets(self):
        with tempfile.TemporaryDirectory() as td:
            writer = RegistryWriter(td)
            snapshot = {
                'BTC': {
                    'strategies': {'macd_trend_continuation': {'status': 'candidate', 'execution_ready': True, 'last_price': 123.4}},
                    'regime_state': {'regime': 'uptrend', 'confidence': 0.7},
                }
            }
            writer.write_snapshot(snapshot)
            writer.append_strategy_candidates(snapshot)
            writer.append_strategy_specs([{'spec_id': 's1'}])
            writer.append_playbook_packets([{'packet_version': 'playbook_bridge_v1'}])
            root = Path(td)
            self.assertTrue((root / 'latest_snapshot.json').exists())
            self.assertTrue((root / 'registry_runs.jsonl').exists())
            self.assertTrue((root / 'strategy_specs.jsonl').exists())
            self.assertTrue((root / 'playbook_packets.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
