from __future__ import annotations

import unittest
from unittest.mock import patch
from regime_engine import classify_regime
from realtime_engine import ResearchEngine, SymbolState

class TestLogicFixes(unittest.TestCase):
    def test_range_chop_fires_with_nonzero_macd(self):
        """range_chop equivalent (sideways_low_normal_vol) must be reachable when bb narrow + z low, even if macd != 0"""
        r = classify_regime(
            {'ret_5': 0.001, 'volatility_20': 0.008},
            {'MACD': 0.01, 'BollingerWidth': 0.02, 'ZScore_Close': 0.3}
        )
        self.assertEqual(r['regime'], 'sideways_low_normal_vol', f"Expected sideways_low_normal_vol, got {r['regime']}")
        self.assertTrue(r['tradable'])

    def test_uptrend_requires_min_ret5(self):
        """ret_5 noise (0.0001) must NOT classify as uptrend equivalent (bull_low_normal_vol)"""
        r = classify_regime(
            {'ret_5': 0.0001, 'volatility_20': 0.01},
            {'MACD': 0.001, 'BollingerWidth': 0.05, 'ZScore_Close': 0.1}
        )
        self.assertNotIn(r['regime'], ['bull_low_normal_vol', 'bull_high_vol'], f"Noise ret_5 should not trigger bull trend, got {r['regime']}")

    def test_prev_bollinger_width_is_stale_not_current(self):
        """prev_bollinger_width must reflect PREVIOUS bar, not current"""
        engine = ResearchEngine(symbols=['BTC'])
        state = engine.states['BTC']
        state.indicators['BollingerWidth'] = 0.12   # old value
        with (
            patch('realtime_engine.compute_factors_np', return_value={}),
            patch('realtime_engine.compute_indicators_np',
                  return_value={'BollingerWidth': 0.31}),  # new value
            patch.object(engine, '_compute_micro_factors'),
            patch.object(engine, '_compute_regime'),
            patch.object(engine, '_compute_signals'),
            patch.object(engine, '_compute_strategies'),
            patch.object(engine, '_compute_risk'),
            patch.object(engine, '_compute_validation'),
            patch.object(engine, '_dispatch_paper_trades'),
        ):
            engine._refresh_state('BTC')
        # prev must be OLD value (0.12), not new (0.31)
        self.assertEqual(state.prev_bollinger_width, 0.12,
            f"Expected prev=0.12 (old), got {state.prev_bollinger_width}")
        self.assertEqual(state.indicators['BollingerWidth'], 0.31)

    def test_strategies_require_35_bars(self):
        """Strategies must NOT fire before 35 bars (MACD not valid yet)"""
        engine = ResearchEngine(symbols=['BTC'])
        state = engine.states['BTC']
        for i in range(34):   # 34 bars — one short of threshold
            state.bars.append(type('B', (), {'close': 100.0, 'volume': 1.0})())
        state.regime_state = {'tradable': True, 'regime': 'uptrend', 'allowed_signal_families': []}
        state.signals = {
            'macd_trend_continuation': {'active': True, 'direction': 'long'},
        }
        engine._compute_strategies(state)
        self.assertFalse(state.strategies['macd_trend_continuation']['logic_ready'],
            "Should not be logic_ready with only 34 bars")
