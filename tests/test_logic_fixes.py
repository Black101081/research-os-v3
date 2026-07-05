from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app import _resolve_take_profit
from factor_math import ema_np
from indicator_keys import (
    BOLLINGER_SQUEEZE_THRESHOLD,
    ZSCORE_ENTRY_SHORT_THRESHOLD,
)
from realtime_engine import ResearchEngine
from regime_engine import classify_regime
from research_brief_generator import generate_playbook_code
from signal_orchestrator import evaluate_supported_signals


class LogicFixTests(unittest.TestCase):
    def test_high_volatility_regime_is_not_tradable(self):
        regime = classify_regime(
            {'ret_5': 0.02, 'volatility_20': 0.05},
            {'MACD': 0.0, 'BollingerWidth': 0.05, 'ZScore_Close': 0.0},
        )
        self.assertEqual(regime['regime'], 'high_volatility')
        self.assertFalse(regime['tradable'])

    def test_bollinger_squeeze_breakout_uses_previous_width(self):
        signals = evaluate_supported_signals(
            'BTC',
            {},
            {'BBANDS_upper': 100.0, 'RelativeVolume': 1.2},
            {'regime': 'uptrend', 'tradable': True},
            last_close=101.0,
            prev_bollinger_width=BOLLINGER_SQUEEZE_THRESHOLD,
        )
        signal = signals['bollinger_squeeze_breakout']
        self.assertTrue(signal['active'])
        self.assertTrue(signal['why']['was_squeezing'])
        self.assertEqual(signal['why']['prev_bollinger_width'], BOLLINGER_SQUEEZE_THRESHOLD)

    def test_refresh_state_preserves_previous_bollinger_width_before_update(self):
        engine = ResearchEngine(symbols=['BTC'])
        state = engine.states['BTC']
        state.indicators['BollingerWidth'] = 0.12
        state.bars.append(type('BarLike', (), {'close': 100.0, 'volume': 1.0})())
        with (
            patch('realtime_engine.compute_factors_np', return_value={}),
            patch('realtime_engine.compute_indicators_np', return_value={'BollingerWidth': 0.31}),
            patch.object(engine, '_compute_micro_factors'),
            patch.object(engine, '_compute_regime'),
            patch.object(engine, '_compute_signals'),
            patch.object(engine, '_compute_strategies'),
            patch.object(engine, '_compute_risk'),
            patch.object(engine, '_compute_validation'),
        ):
            engine._refresh_state('BTC')
        self.assertEqual(state.prev_bollinger_width, 0.12)
        self.assertEqual(state.indicators['BollingerWidth'], 0.31)

    def test_compute_strategies_infers_non_long_entry_sides(self):
        engine = ResearchEngine(symbols=['BTC'])
        state = engine.states['BTC']
        for i in range(40):
            state.bars.append(type('BarLike', (), {'close': 100.0 + i, 'volume': 1.0})())
        state.last_trade = 99.0
        state.updated_at = '2026-07-05T00:00:00+00:00'
        state.regime_state = {'tradable': True, 'regime': 'range_chop'}
        state.indicators = {
            'ZScore_Close': ZSCORE_ENTRY_SHORT_THRESHOLD,
            'MACD': -1.0,
            'MACD_signal': 1.0,
            'BBANDS_mid': 100.0,
        }
        state.signals = {
            'zscore_recenter': {'active': False},
            'macd_trend_continuation': {'active': False},
            'bollinger_squeeze_breakout': {'active': False},
        }
        engine._compute_strategies(state)
        self.assertEqual(state.strategies['zscore_recenter']['entry_side'], 'short')
        self.assertEqual(state.strategies['macd_trend_continuation']['entry_side'], 'short')
        self.assertEqual(state.strategies['bollinger_squeeze_breakout']['entry_side'], 'short')

    def test_generated_playbook_uses_shared_squeeze_threshold_default(self):
        code = generate_playbook_code('BTC', 'bollinger_squeeze_breakout', {}, {})
        self.assertIn(f'getattr(self, "width_threshold", {BOLLINGER_SQUEEZE_THRESHOLD})', code)

    def test_take_profit_uses_risk_packet_then_clamped_fallback(self):
        self.assertEqual(
            _resolve_take_profit(100.0, 'long', {'take_profit_price': 123.0}, {'indicators': {'BollingerWidth': 0.5}}),
            123.0,
        )
        self.assertAlmostEqual(
            _resolve_take_profit(100.0, 'long', {}, {'indicators': {'BollingerWidth': 0.5}}),
            110.0,
        )
        self.assertAlmostEqual(
            _resolve_take_profit(100.0, 'short', {}, {'indicators': {'BollingerWidth': 0.001}}),
            99.0,
        )

    def test_ema_np_returns_single_value_for_singleton_series(self):
        self.assertEqual(ema_np([42.0], 9), 42.0)


if __name__ == '__main__':
    unittest.main()
