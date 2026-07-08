import unittest
from factor_math import calc_cvd_slope, calc_decayed_flow_imbalance
from risk_engine import compute_position_size
from paper_broker import PaperBroker
from quality_gate_models import QualifiedSignal
from signal_library import SignalResult

class TestProfitOptimization(unittest.TestCase):
    def test_cvd_slope(self):
        prices = [100.0] * 20
        sizes = [1.0] * 20
        sides = ["B"] * 20  # All buys: CVD going up
        slope = calc_cvd_slope(prices, sizes, sides, 10)
        self.assertGreater(slope, 0.0)

    def test_decayed_flow_imbalance(self):
        sizes = [1.0, 2.0, 3.0]
        sides = ["B", "A", "B"]
        tfi = calc_decayed_flow_imbalance(sizes, sides, 3, 0.05)
        # Net positive buy delta
        self.assertGreater(tfi, 0.0)

    def test_regime_kelly_sizing(self):
        indicators = {"atr_pct_14": 0.02}
        risk_config = {
            "sizing_model": "kelly",
            "account_equity": 10000.0,
            "kelly_fraction": 0.25,
            "max_kelly_pct": 0.05,
            "rr_ratio": 2.0
        }
        portfolio_state = {"balance": 10000.0}
        regime_state = {
            "confidence": 0.8,
            "allowed_signal_families": ["continuation"]
        }
        res = compute_position_size(
            "BTC", 60000.0, indicators, risk_config, portfolio_state, regime_state
        )
        self.assertEqual(res["sizing_model_used"], "kelly")
        self.assertGreater(res["target_quantity"], 0.0)

    def test_paper_broker_limit_fill_and_chase(self):
        broker = PaperBroker(initial_balance=10000.0)
        # Clear positions to ensure clean test
        broker.clear_all_positions()
        
        # Construct actual signal and qualified signal
        sig = SignalResult(
            signal_id="test_sig_123",
            symbol="BTC",
            family="macd_trend_continuation",
            interval="15m",
            asset_role="anchor",
            fired=True,
            direction="long",
            entry_price=60000.0,
            stop_loss=59000.0,
            take_profit=62000.0,
            take_profit_2=63000.0,
            confidence_score=0.8,
            confluence_votes=3,
            confluence_total=4,
            risk_reward_ratio=2.0,
            atr_at_signal=100.0,
            invalidation_price=59000.0,
            notes=["test_sig"],
            indicators_snapshot={}
        )
        qualified = QualifiedSignal(
            signal=sig,
            position_size_pct=5.0,
            position_size_usd=500.0,
            risk_amount_usd=10.0,
            expected_value_r=0.5,
            market_regime="bullish_trend",
            btc_structure="bullish",
            session_name="london",
            cooldown_key="BTC_macd_trend_continuation",
            qualified_at="2026-07-08T08:00:00Z"
        )
        
        # Submit qualified signal
        res = broker.on_qualified_signal(qualified)
        self.assertTrue(res)
        self.assertEqual(len(broker.pending_orders), 1)
        
        # Process tick that doesn't fill
        broker.process_tick("BTC", 60100.0, "2026-07-08T08:00:00Z")
        self.assertEqual(len(broker.pending_orders), 1)
        self.assertEqual(broker.pending_orders[0]["ticks_waiting"], 1)
        
        # Wait 4 more ticks to trigger chase (total 5)
        for _ in range(4):
            broker.process_tick("BTC", 60100.0, "2026-07-08T08:00:00Z")
        
        # Should have chased: limit price moved to 60100.0, chase_count = 1
        self.assertEqual(broker.pending_orders[0]["chase_count"], 1)
        self.assertEqual(broker.pending_orders[0]["limit_price"], 60100.0)
        
        # Tick that fills
        broker.process_tick("BTC", 60050.0, "2026-07-08T08:00:00Z")
        self.assertEqual(len(broker.pending_orders), 0)
        self.assertEqual(len(broker.positions), 1)

    def test_bb_percentile(self):
        from factor_math import calc_bb_percentile
        bb_widths = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5]
        pct = calc_bb_percentile(bb_widths, window=5)
        # 2.5 is the highest in the last 5 values (1.5, 1.8, 2.0, 2.2, 2.5) -> should be 100.0
        self.assertEqual(pct, 100.0)

    def test_cvd_divergence(self):
        from factor_math import compute_divergence
        # Bullish divergence: price printing lower lows, but indicator printing higher lows
        closes = [10.0, 9.5, 9.2, 9.0, 9.5, 9.2, 9.0, 8.8, 8.5, 9.0, 9.2, 9.5]
        cvd    = [110.0, 105.0, 102.0, 100.0, 105.0, 108.0, 110.0, 108.0, 105.0, 110.0, 112.0, 115.0]
        score = compute_divergence(closes, cvd, fractal_window=1, max_lookback=10)
        self.assertLess(score, 0.0)

    def test_paper_broker_trailing_stops(self):
        broker = PaperBroker(initial_balance=10000.0)
        broker.clear_all_positions()
        
        sig = SignalResult(
            signal_id="test_trail_123",
            symbol="BTC",
            family="macd_trend_continuation",
            interval="15m",
            asset_role="anchor",
            fired=True,
            direction="long",
            entry_price=60000.0,
            stop_loss=58000.0,
            take_profit=66000.0,
            take_profit_2=68000.0,
            confidence_score=0.8,
            confluence_votes=3,
            confluence_total=4,
            risk_reward_ratio=3.0,
            atr_at_signal=100.0,
            invalidation_price=58000.0,
            notes=["test_trail"],
            indicators_snapshot={}
        )
        qualified = QualifiedSignal(
            signal=sig,
            position_size_pct=5.0,
            position_size_usd=500.0,
            risk_amount_usd=10.0,
            expected_value_r=0.5,
            market_regime="bullish_trend",
            btc_structure="bullish",
            session_name="london",
            cooldown_key="BTC_macd_trend_continuation",
            qualified_at="2026-07-08T08:00:00Z"
        )
        
        # Submit
        broker.on_qualified_signal(qualified)
        
        # Fill immediately at entry_price
        broker.process_tick("BTC", 60000.0, "2026-07-08T08:00:00Z")
        self.assertEqual(len(broker.positions), 1)
        
        pos_key = "BTC_macd_trend_continuation"
        pos = broker.positions[pos_key]
        self.assertEqual(pos["stop_loss"], 58000.0)
        self.assertEqual(pos["breakeven_triggered"], False)
        
        # Price moves up by 1.0R (62000.0) -> triggers breakeven and trails up to 60200.0
        broker.process_tick("BTC", 62000.0, "2026-07-08T08:00:05Z", {"atr_pct_14": 2.0})
        pos = broker.positions[pos_key]
        self.assertEqual(pos["stop_loss"], 60200.0)
        self.assertTrue(pos["breakeven_triggered"])
        
        # Price moves up further to 65000.0 -> trails stop-loss
        # ATR trail distance = 1.5 * 2% * 60000 = 1800
        # stop_loss = 65000 - 1800 = 63200
        broker.process_tick("BTC", 65000.0, "2026-07-08T08:00:10Z", {"atr_pct_14": 2.0})
        pos = broker.positions[pos_key]
        self.assertEqual(pos["stop_loss"], 63200.0)

