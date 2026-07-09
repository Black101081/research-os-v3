import unittest
import numpy as np
from factor_math import wma_np, hma_np, rsi_hma_np
from signal_models import SignalResult
from quality_gate import QualityGate, QualityGateConfig
from quality_gate_models import SessionConfig, RegimeConfig, StatisticalConfig, SizingConfig, GateRejection

class TestThesisAndIndicatorUpgrades(unittest.TestCase):
    def test_wma_and_hma_np(self):
        # 1. Test WMA
        values = [1.0, 2.0, 3.0]
        # weights = [1, 2, 3] -> dot product = 1*1 + 2*2 + 3*3 = 14. sum = 6. -> 14/6 = 2.3333
        self.assertAlmostEqual(wma_np(values, 3), 14/6.0)
        
        # 2. Test HMA
        # Ensure it runs without exception
        values_large = list(range(1, 50))
        h_val = hma_np(values_large, 20)
        self.assertTrue(isinstance(h_val, float))
        
        # 3. Test RSI HMA
        rsi_val = rsi_hma_np(values_large, 14)
        self.assertTrue(0.0 <= rsi_val <= 100.0)

    def test_quality_gate_dynamic_thesis_and_mtf(self):
        # Build mtf engine mock/stub
        class MockTFState:
            def __init__(self, interval, last_close, indicators):
                self.interval = interval
                self.last_close = last_close
                self.indicators = indicators

        class MockSymbolState:
            def __init__(self, last_close=60000.0):
                self.last_close = last_close
                self.tfs = {
                    "15m": MockTFState("15m", last_close, {"adx_14": 25.0, "rsi_14": 45.0, "BollingerWidth_ZScore": 1.8}),
                    "1h": MockTFState("1h", last_close, {"EMA_20": 58000.0})  # 1h Trend is Bullish (close 60000 > EMA 58000)
                }
            def get_tf(self, tf):
                return self.tfs.get(tf)

        mtf_mock = {"BTC": MockSymbolState()}
        
        # Instantiate QualityGate
        cfg = QualityGateConfig(
            session=SessionConfig(enabled=False),
            regime=RegimeConfig(enabled=False),
            statistical=StatisticalConfig(enabled=False),
            sizing=SizingConfig(enabled=False)
        )
        gate = QualityGate(cfg, mtf_mock)
        
        # Construct long signal (1h macro trend is bullish, close 60000 > EMA 58000, should pass MTF)
        sig = SignalResult(
            signal_id="BTC_macd_trend_continuation_15m_test",
            symbol="BTC",
            family="macd_trend_continuation",
            interval="15m",
            asset_role="anchor",
            fired=True,
            direction="long",
            entry_price=60000.0,
            stop_loss=59000.0,
            take_profit=62000.0,
            confidence_score=0.8,
            confluence_votes=3,
            confluence_total=4,
            risk_reward_ratio=2.0
        )
        
        qs = gate.evaluate(sig)
        self.assertIsNotNone(qs)
        # Ensure dynamic thesis is generated
        self.assertTrue("BTC" in qs.thesis)
        self.assertTrue("ADX=" in qs.thesis)
        self.assertTrue("Target scaled by 1.3x" in qs.thesis)

        # Construct short signal (close 60000 > EMA 58000 -> 1h macro trend is bullish -> short continuation should fail)
        sig_short = SignalResult(
            signal_id="BTC_macd_trend_continuation_15m_short",
            symbol="BTC",
            family="macd_trend_continuation",
            interval="15m",
            asset_role="anchor",
            fired=True,
            direction="short",
            entry_price=60000.0,
            stop_loss=61000.0,
            take_profit=58000.0,
            confidence_score=0.8,
            confluence_votes=3,
            confluence_total=4,
            risk_reward_ratio=2.0
        )
        qs_short = gate.evaluate(sig_short)
        self.assertTrue(isinstance(qs_short, GateRejection))
        self.assertTrue("Blocked by MTF" in qs_short.block_reason)
