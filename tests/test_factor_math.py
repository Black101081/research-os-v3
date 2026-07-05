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
    compute_indicators_np
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


if __name__ == "__main__":
    unittest.main()
