from __future__ import annotations

import unittest
import numpy as np
from factor_math import (
    ema_np,
    macd_np,
    bollinger_bands_np,
    zscore_np,
    rel_volume_np,
    flow_imbalance_np,
    compute_factors_np,
    compute_indicators_np,
    rsi_np,
    atr_np,
    compute_divergence,
    find_fractal_peaks,
    find_fractal_troughs,
    macd_history_np,
    rsi_history_np
)


class TestFactorMath(unittest.TestCase):
    def test_ema_np(self):
        values = [10.0, 11.0, 12.0, 13.0, 14.0]
        res = ema_np(values, 3)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res, 13.0625)
        self.assertIsNone(ema_np([], 3))

    def test_macd_np(self):
        closes = [100.0 + i for i in range(50)]
        res = macd_np(closes)
        self.assertIn("MACD", res)
        self.assertIn("MACD_signal", res)
        self.assertIn("MACD_hist", res)
        self.assertAlmostEqual(res["MACD_hist"], res["MACD"] - res["MACD_signal"])

    def test_bollinger_bands_np(self):
        closes = [10.0, 11.0, 12.0, 13.0, 14.0]
        res = bollinger_bands_np(closes, period=5, num_std=2.0)
        self.assertIn("BBANDS_mid", res)
        self.assertIn("BBANDS_upper", res)
        self.assertIn("BBANDS_lower", res)
        self.assertIn("BollingerWidth", res)
        self.assertAlmostEqual(res["BBANDS_mid"], 12.0)

    def test_zscore_np(self):
        closes = [10.0, 11.0, 12.0, 13.0, 14.0]
        res = zscore_np(closes, period=5)
        self.assertIsInstance(res, float)
        self.assertTrue(res > 0) # 14 is above mean of 12

    def test_rel_volume_np(self):
        volumes = [100.0] * 20
        volumes[-1] = 200.0
        res = rel_volume_np(volumes, period=20)
        self.assertAlmostEqual(res, 2.0)

    def test_flow_imbalance_np(self):
        sizes = [10.0, 20.0, 30.0]
        sides = ["B", "A", "B"]
        res = flow_imbalance_np(sizes, sides, window=3)
        self.assertAlmostEqual(res, (10.0 - 20.0 + 30.0) / 60.0)

    def test_compute_factors_np(self):
        closes = [100.0 + i for i in range(100)]
        volumes = [1000.0] * 100
        res = compute_factors_np(closes, volumes)
        self.assertIn("ret_1", res)
        self.assertIn("ret_5", res)
        self.assertIn("zscore_close_20", res)
        self.assertIn("volatility_20", res)
        self.assertIn("ema_spread_8_21", res)
        self.assertIn("rel_volume_20", res)

    def test_compute_indicators_np(self):
        closes = [100.0 + i for i in range(100)]
        factors = {"zscore_close_20": 1.5, "rel_volume_20": 2.0}
        res = compute_indicators_np(closes, factors)
        self.assertIn("BBANDS_mid", res)
        self.assertIn("MACD", res)
        self.assertIn("ZScore_Close", res)
        self.assertIn("RelativeVolume", res)

    def test_ema_against_pandas(self):
        import pandas as pd
        closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.5, 17.2, 19.1]
        for period in [3, 5, 8]:
            pd_val = pd.Series(closes).ewm(span=period, adjust=False).mean().iloc[-1]
            np_val = ema_np(closes, period)
            self.assertIsNotNone(np_val)
            self.assertAlmostEqual(np_val, pd_val, places=6)

    def test_rsi_np(self):
        closes = [100.0] * 30
        res = rsi_np(closes, 14)
        self.assertEqual(res, 50.0) # Flat prices = neutral RSI
        
        # Increasing prices
        up_closes = [100.0 + i for i in range(30)]
        res_up = rsi_np(up_closes, 14)
        self.assertTrue(res_up > 50.0)
        
    def test_atr_np(self):
        highs = [102.0] * 20
        lows = [98.0] * 20
        closes = [100.0] * 20
        res = atr_np(highs, lows, closes, 14)
        self.assertAlmostEqual(res, 4.0) # True range is consistently 4
        
    def test_compute_divergence(self):
        # 1. Bearish Divergence
        closes = [10.0, 11.0, 12.0, 11.0, 10.0, 11.0, 13.0, 11.0, 10.0]
        indicator = [5.0, 6.0, 7.0, 6.0, 5.0, 5.5, 6.5, 5.5, 4.0]
        score = compute_divergence(closes, indicator, fractal_window=2, max_lookback=30)
        self.assertTrue(score > 0.0)
        self.assertAlmostEqual(score, 0.595238, places=4)

        # 2. Bullish Divergence
        closes_bull = [20.0, 19.0, 18.0, 19.0, 20.0, 18.0, 17.0, 18.0, 20.0]
        indicator_bull = [5.0, 4.0, 3.0, 4.0, 5.0, 4.5, 3.5, 4.5, 6.0]
        score_bull = compute_divergence(closes_bull, indicator_bull, fractal_window=2, max_lookback=30)
        self.assertTrue(score_bull < 0.0)
        self.assertAlmostEqual(score_bull, -0.925925, places=4)

        # 3. Staleness Check
        stale_score = compute_divergence(closes, indicator, fractal_window=2, max_lookback=1)
        self.assertEqual(stale_score, 0.0)

        # 4. Low Data Check
        low_data_score = compute_divergence([1.0, 2.0], [1.0, 2.0])
        self.assertEqual(low_data_score, 0.0)

    def test_find_fractal_peaks_troughs(self):
        values = [10.0, 11.0, 12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0]
        peaks = find_fractal_peaks(values, window=2)
        self.assertEqual(peaks, [2])
        
        troughs = find_fractal_troughs(values, window=2)
        self.assertEqual(troughs, [6])

    def test_latency_benchmark(self):
        import time
        closes = [100.0 + i * 0.1 for i in range(500)]
        volumes = [1000.0] * 500
        
        # Warmup
        for _ in range(10):
            compute_factors_np(closes, volumes)
            
        t0 = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            factors = compute_factors_np(closes, volumes)
            compute_indicators_np(closes, factors)
        t1 = time.perf_counter()
        
        avg_time_ms = ((t1 - t0) / iterations) * 1000
        print(f"\n[BENCHMARK] Average latency for 500 bars: {avg_time_ms:.4f} ms")
        self.assertTrue(avg_time_ms < 5.0, f"Latency is {avg_time_ms:.2f} ms (expected < 5 ms)")


if __name__ == "__main__":
    unittest.main()
