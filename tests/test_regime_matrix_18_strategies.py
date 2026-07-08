from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from regime_engine import classify_regime
from signal_library import (
    signal_macd_continuation,
    signal_ema_pullback_buy,
    signal_high_vol_breakout,
    signal_range_boundary_fade,
    evaluate_all_signals
)
from multi_tf_state import MultiTFSymbolState, TFState


class TestRegimeMatrix18Strategies(unittest.TestCase):
    def test_3x3_regime_classification(self):
        # 1. Bull Low-Normal Vol (Group A)
        r = classify_regime(
            {'volatility_20': 0.008, 'ema_spread_8_21': 0.005},
            {'adx_14': 18.0}
        )
        self.assertEqual(r['regime'], 'bull_low_normal_vol')
        self.assertEqual(r['group'], 'Group A')
        self.assertIn('macd_trend_continuation', r['allowed_strategies'])

        # 2. Bull High Vol (Group B)
        r = classify_regime(
            {'volatility_20': 0.035, 'ema_spread_8_21': 0.006},
            {'adx_14': 30.0}
        )
        self.assertEqual(r['regime'], 'bull_high_vol')
        self.assertEqual(r['group'], 'Group B')
        self.assertIn('high_vol_breakout', r['allowed_strategies'])

        # 3. Sideways High Vol (Group C)
        r = classify_regime(
            {'volatility_20': 0.030, 'ema_spread_8_21': 0.000},
            {'adx_14': 15.0}
        )
        self.assertEqual(r['regime'], 'sideways_high_vol')
        self.assertEqual(r['group'], 'Group C')
        self.assertIn('range_boundary_fade', r['allowed_strategies'])

        # 4. Bear High Vol (Group D)
        r = classify_regime(
            {'volatility_20': 0.032, 'ema_spread_8_21': -0.005},
            {'adx_14': 28.0}
        )
        self.assertEqual(r['regime'], 'bear_high_vol')
        self.assertEqual(r['group'], 'Group D')
        self.assertIn('high_vol_breakdown', r['allowed_strategies'])

        # 5. Bear Low-Normal Vol (Group E)
        r = classify_regime(
            {'volatility_20': 0.010, 'ema_spread_8_21': -0.004},
            {'adx_14': 20.0}
        )
        self.assertEqual(r['regime'], 'bear_low_normal_vol')
        self.assertEqual(r['group'], 'Group E')
        self.assertIn('bearish_trend_continuation', r['allowed_strategies'])

        # 6. Sideways Low-Normal Vol (Group F)
        r = classify_regime(
            {'volatility_20': 0.005, 'ema_spread_8_21': 0.000},
            {'adx_14': 12.0}
        )
        self.assertEqual(r['regime'], 'sideways_low_normal_vol')
        self.assertEqual(r['group'], 'Group F')
        self.assertIn('mean_reversion_squeeze', r['allowed_strategies'])

    def test_signals_evaluations_run(self):
        # Create a mock symbol state with 50 bars
        sym_state = MultiTFSymbolState(symbol="BTC")
        tf_state = TFState(symbol="BTC", interval="15m")
        
        # Add 50 mock bars
        for i in range(50):
            bar = MagicMock()
            bar.open = 100.0 + i
            bar.high = 105.0 + i
            bar.low = 95.0 + i
            bar.close = 102.0 + i
            bar.volume = 1000.0
            tf_state.bars.append(bar)
            
        tf_state.indicators = {
            "adx_14": 30.0,
            "MACD": 1.2,
            "MACD_signal": 0.8,
            "MACD_histogram": 0.4,
            "rsi_14": 62.0,
            "ema_spread_8_21": 0.05,
            "obv_slope_10": 2.5,
            "atr_14": 2.0,
            "ema_20": 140.0,
            "ema_50": 135.0,
            "volume_ratio": 1.8,
            "bb_pct_20": 0.98,
            "kc_upper": 150.0,
            "parkinson_volatility_20": 0.022,
            "stoch_k": 85.0,
            "stoch_d": 90.0,
            "squeeze_score": 0.80
        }
        
        sym_state.tf_states["15m"] = tf_state
        
        # Evaluate all signals
        batch = evaluate_all_signals(sym_state, "15m", "anchor")
        self.assertEqual(batch.symbol, "BTC")
        self.assertEqual(batch.interval, "15m")
        self.assertEqual(len(batch.results), 18)
        
        # Test specific signals
        macd_sig = next(r for r in batch.results if r.family == "macd_trend_continuation")
        self.assertTrue(macd_sig.fired)
        self.assertEqual(macd_sig.direction, "long")
        
        vol_breakout = next(r for r in batch.results if r.family == "high_vol_breakout")
        self.assertTrue(vol_breakout.fired)
        
        # Verify that all 18 signal runs compile and evaluate without throwing exceptions
        for res in batch.results:
            self.assertIsNotNone(res.signal_id)
