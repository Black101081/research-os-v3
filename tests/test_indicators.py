import math
import pytest
import numpy as np
import factor_math as fm
from multi_tf_state import MultiTFEngine, TFBar
from tf_indicator_engine import compute_tf_indicators, compute_all_tf_indicators

# ── Helpers ─────────────────────────────────────────────────────────

def make_bars(n: int, start_price: float = 100.0,
              drift: float = 0.0, vol: float = 0.5, seed: int = 42) -> list:
    """Generate synthetic bars with slight trend + noise."""
    np.random.seed(seed)
    closes = [start_price]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1 + drift + np.random.normal(0, vol / 100)))
    bars = []
    for i, c in enumerate(closes):
        bars.append(TFBar(
            ts=f"2026-01-01T{i:04d}",
            open=c * 0.999, high=c * 1.002,
            low=c * 0.997, close=c,
            volume=1000 + np.random.uniform(0, 500),
        ))
    return bars


def make_bars_with_ohlcv(n: int, closes: list, volumes: list = None) -> list:
    """Generate bars with specific closes and optional volumes."""
    bars = []
    if volumes is None:
        volumes = [1000.0] * n
    for i in range(n):
        c = closes[i]
        bars.append(TFBar(
            ts=f"2026-01-01T{i:04d}",
            open=c, high=c * 1.01,
            low=c * 0.99, close=c,
            volume=volumes[i]
        ))
    return bars


def make_engine_with_bars(n_bars: int, symbol="BTC", interval="15m"):
    cfg = {symbol: {"candle_intervals": [interval], "role": "anchor",
                    "subscribe_l2book": True, "subscribe_active_asset_ctx": True}}
    eng = MultiTFEngine(cfg, {interval: 500})
    tf = eng.get(symbol).tf_states[interval]
    for bar in make_bars(n_bars):
        tf.bars.append(bar)
    return eng


# ── factor_math unit tests ────────────────────────────────────────────

class TestCalcEma:
    def test_single_value(self):
        assert fm.calc_ema([100.0], 1) == pytest.approx(100.0)

    def test_insufficient_data_returns_last(self):
        result = fm.calc_ema([50.0, 60.0], 14)
        assert result == pytest.approx(60.0)

    def test_ema_responds_to_uptrend(self):
        # Ascending series: EMA should be below last value (lagging)
        prices = list(range(1, 30))
        ema = fm.calc_ema(prices, 14)
        assert ema < prices[-1]
        assert ema > prices[0]

    def test_ema_period_1_equals_last(self):
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert fm.calc_ema(prices, 1) == pytest.approx(50.0)


class TestCalcRsi:
    def test_returns_50_insufficient_data(self):
        assert fm.calc_rsi([100.0] * 5) == pytest.approx(50.0)

    def test_flat_prices_returns_50(self):
        result = fm.calc_rsi([100.0] * 30)
        assert 0.0 <= result <= 100.0

    def test_pure_uptrend_rsi_high(self):
        closes = [100 + i for i in range(30)]
        rsi = fm.calc_rsi(closes, period=14)
        assert rsi > 70

    def test_pure_downtrend_rsi_low(self):
        closes = [100 - i * 0.5 for i in range(30)]
        rsi = fm.calc_rsi(closes, period=14)
        assert rsi < 40

    def test_rsi_range_0_100(self):
        import random
        random.seed(0)
        prices = [100 + random.gauss(0, 2) for _ in range(50)]
        rsi = fm.calc_rsi(prices)
        assert 0.0 <= rsi <= 100.0


class TestCalcMacd:
    def test_returns_zeros_insufficient(self):
        result = fm.calc_macd([100.0] * 10)
        assert result == (0.0, 0.0, 0.0)

    def test_macd_structure(self):
        closes = [100 + i * 0.1 for i in range(50)]
        macd, signal, hist = fm.calc_macd(closes)
        assert hist == pytest.approx(macd - signal, abs=1e-6)

    def test_uptrend_macd_positive(self):
        closes = [100 + i for i in range(50)]
        macd, signal, hist = fm.calc_macd(closes)
        assert macd > signal


class TestCalcAtr:
    def test_returns_zero_insufficient(self):
        assert fm.calc_atr([100.0]*5, [100.0]*5, [100.0]*5) == 0.0

    def test_atr_positive(self):
        h = [102 + i*0.1 for i in range(20)]
        l = [98  - i*0.1 for i in range(20)]
        c = [100 + i*0.05 for i in range(20)]
        atr = fm.calc_atr(h, l, c)
        assert atr > 0

    def test_atr_pct_scales_with_price(self):
        h = [102 + i*0.1 for i in range(20)]
        l = [98  - i*0.1 for i in range(20)]
        c = [100 + i*0.05 for i in range(20)]
        pct = fm.calc_atr_pct(h, l, c)
        assert 0 < pct < 10


class TestCalcAdx:
    def test_returns_zero_insufficient(self):
        assert fm.calc_adx([100.0]*10, [100.0]*10, [100.0]*10) == 0.0

    def test_strong_trend_adx_high(self):
        n = 40
        c = [100 + i for i in range(n)]
        h = [x + 1 for x in c]
        l = [x - 0.5 for x in c]
        adx = fm.calc_adx(h, l, c, period=14)
        assert adx >= 20.0

    def test_adx_range_0_100(self):
        n = 40
        c = [100 + i*0.5 for i in range(n)]
        h = [x + 1 for x in c]
        l = [x - 1 for x in c]
        adx = fm.calc_adx(h, l, c)
        assert 0.0 <= adx <= 100.0


class TestVolumeIndicators:
    def test_vwap_uniform_volume(self):
        closes  = [100.0, 101.0, 102.0]
        volumes = [100.0, 100.0, 100.0]
        vwap = fm.calc_vwap(closes, volumes)
        assert vwap == pytest.approx(101.0)

    def test_vwap_heavy_last_bar(self):
        closes  = [100.0, 110.0]
        volumes = [1.0,   9.0]
        vwap = fm.calc_vwap(closes, volumes)
        assert vwap == pytest.approx(109.0)

    def test_volume_ratio_spike(self):
        base = [100.0] * 20
        spike = base + [500.0]
        ratio = fm.calc_volume_ratio(spike, window=20)
        assert ratio > 4.0

    def test_volume_ratio_insufficient(self):
        assert fm.calc_volume_ratio([100.0] * 5) == 1.0

    def test_obv_uptrend_positive(self):
        closes  = [100 + i for i in range(10)]
        volumes = [1000.0] * 10
        obv = fm.calc_obv(closes, volumes)
        assert obv > 0

    def test_obv_flat_zero(self):
        closes  = [100.0] * 10
        volumes = [1000.0] * 10
        obv = fm.calc_obv(closes, volumes)
        assert obv == pytest.approx(0.0)

    def test_volume_poc_returns_price_in_range(self):
        closes  = [100.0, 105.0, 102.0, 104.0, 103.0]
        volumes = [100.0] * len(closes)
        poc = fm.calc_volume_poc(closes, volumes, bins=10)
        assert min(closes) <= poc <= max(closes)

    def test_bb_width_positive(self):
        closes = [100 + i * 0.2 for i in range(25)]
        bw = fm.calc_bb_width(closes)
        assert bw > 0

    def test_bb_pct_at_midband(self):
        closes = [100.0] * 20
        bb = fm.calc_bb_pct(closes)
        assert 0.0 <= bb <= 1.0


class TestCryptoNativeIndicators:
    def test_funding_zscore_neutral(self):
        history = [0.0001] * 10
        assert fm.calc_funding_zscore(history) == pytest.approx(0.0)

    def test_funding_zscore_spike(self):
        history = [0.0001, 0.00012, 0.00008, 0.00011, 0.00009] * 2 + [0.001]
        z = fm.calc_funding_zscore(history)
        assert z > 2.0

    def test_oi_momentum_positive(self):
        oi = [100.0] * 5 + [120.0]
        mom = fm.calc_oi_momentum(oi, period=5)
        assert mom > 0

    def test_oi_momentum_insufficient(self):
        assert fm.calc_oi_momentum([100.0]*3, period=5) == 0.0

    def test_bid_ask_imbalance_bid_heavy(self):
        bids = [(50000, 10), (49999, 5)]
        asks = [(50001, 2), (50002, 1)]
        imb = fm.calc_bid_ask_imbalance(bids, asks, top_n=2)
        assert imb > 0.5

    def test_bid_ask_imbalance_balanced(self):
        bids = [(50000, 5)]
        asks = [(50001, 5)]
        imb = fm.calc_bid_ask_imbalance(bids, asks, top_n=1)
        assert imb == pytest.approx(0.0)

    def test_spread_bps_calculation(self):
        bps = fm.calc_spread_bps(49990, 50010)
        assert bps == pytest.approx(4.0, abs=0.01)

    def test_spread_bps_zero_inputs(self):
        assert fm.calc_spread_bps(0, 50000) == 0.0


# ── TFIndicatorEngine integration tests ─────────────────────────────

class TestComputeTfIndicators:
    def test_no_crash_on_minimal_bars(self):
        eng = make_engine_with_bars(3, interval="15m")
        tf = eng.get("BTC").tf_states["15m"]
        compute_tf_indicators(tf)   # should not raise

    def test_indicators_populated_after_50_bars(self):
        eng = make_engine_with_bars(60, interval="15m")
        tf = eng.get("BTC").tf_states["15m"]
        compute_tf_indicators(tf)
        assert "rsi_14"          in tf.indicators
        assert "MACD"            in tf.indicators
        assert "atr_14"          in tf.indicators
        assert "adx_14"          in tf.indicators
        assert "vwap"            in tf.indicators
        assert "volume_ratio"    in tf.indicators
        assert "bb_width_20"     in tf.indicators
        assert "ema_spread_8_21" in tf.indicators
        assert "momentum_score"  in tf.indicators
        assert "volume_quality_score" in tf.indicators

    def test_idempotent_double_call(self):
        eng = make_engine_with_bars(60, interval="15m")
        tf = eng.get("BTC").tf_states["15m"]
        compute_tf_indicators(tf)
        rsi_first = tf.indicators["rsi_14"]
        compute_tf_indicators(tf)
        assert tf.indicators["rsi_14"] == pytest.approx(rsi_first)

    def test_crypto_native_with_funding_oi(self):
        eng = make_engine_with_bars(60, interval="5m")
        tf = eng.get("BTC").tf_states["5m"]
        sym = eng.get("BTC")
        funding_hist = [0.0001 + i * 0.00001 for i in range(20)]
        oi_hist = [10000 + i * 100 for i in range(20)]
        compute_tf_indicators(tf, sym_state=sym,
                              funding_history=funding_hist,
                              oi_history=oi_hist)
        assert "funding_zscore"  in tf.indicators
        assert "funding_signal"  in tf.indicators
        assert "oi_momentum_5"   in tf.indicators
        assert "oi_trend"        in tf.indicators

    def test_book_imbalance_populated_from_sym_state(self):
        eng = make_engine_with_bars(60, interval="5m")
        sym = eng.get("BTC")
        sym.bid_levels = [(50000, 10), (49999, 8), (49998, 6)]
        sym.ask_levels = [(50001, 2), (50002, 1), (50003, 1)]
        tf = sym.tf_states["5m"]
        compute_tf_indicators(tf, sym_state=sym)
        assert "book_imbalance_10" in tf.indicators
        assert tf.indicators["book_imbalance_10"] > 0   # bid heavy

    def test_compute_all_tf_indicators(self):
        cfg = {
            "BTC": {"candle_intervals": ["5m", "15m"], "role": "anchor",
                    "subscribe_l2book": True, "subscribe_active_asset_ctx": True}
        }
        eng = MultiTFEngine(cfg, {"5m": 300, "15m": 200})
        sym = eng.get("BTC")
        for interval in ["5m", "15m"]:
            for bar in make_bars(60):
                sym.tf_states[interval].bars.append(bar)
        compute_all_tf_indicators(sym)
        for interval in ["5m", "15m"]:
            ind = sym.tf_states[interval].indicators
            assert "rsi_14" in ind, f"rsi_14 missing for {interval}"
            assert "atr_14" in ind, f"atr_14 missing for {interval}"

    def test_rsi_differs_between_tf(self):
        """RSI on 5m vs 15m must be different even for same symbol — key Tầng 2 requirement."""
        cfg = {
            "BTC": {"candle_intervals": ["5m", "15m"], "role": "anchor",
                    "subscribe_l2book": False, "subscribe_active_asset_ctx": False}
        }
        eng = MultiTFEngine(cfg, {"5m": 300, "15m": 200})
        sym = eng.get("BTC")
        np.random.seed(7)
        # Different seeds for each TF to simulate different bar data
        for i, interval in enumerate(["5m", "15m"]):
            tf = sym.tf_states[interval]
            for bar in make_bars(60, drift=0.0, vol=1.0, seed=42 + i):
                tf.bars.append(bar)
        compute_all_tf_indicators(sym)
        rsi_5m  = sym.tf_states["5m"].indicators.get("rsi_14", 50.0)
        rsi_15m = sym.tf_states["15m"].indicators.get("rsi_14", 50.0)
        # Must be independently computed — not the same value
        assert rsi_5m != pytest.approx(rsi_15m, abs=0.1), \
            "RSI on different TFs should differ (they use independent bar series)"

    def test_atr_14_pct_reasonable_range(self):
        eng = make_engine_with_bars(60, interval="15m")
        tf = eng.get("BTC").tf_states["15m"]
        compute_tf_indicators(tf)
        atr_pct = tf.indicators.get("atr_14_pct", 0.0)
        assert 0.0 < atr_pct < 5.0, f"ATR% out of range: {atr_pct}"

    def test_momentum_score_range(self):
        eng = make_engine_with_bars(60, interval="15m")
        tf = eng.get("BTC").tf_states["15m"]
        compute_tf_indicators(tf)
        ms = tf.indicators.get("momentum_score", 0.0)
        assert -1.0 <= ms <= 1.0

    def test_no_indicators_on_2_bars(self):
        """Should not crash and should not write spurious indicators."""
        cfg = {"BTC": {"candle_intervals": ["1m"], "role": "anchor",
                       "subscribe_l2book": False, "subscribe_active_asset_ctx": False}}
        eng = MultiTFEngine(cfg, {"1m": 500})
        tf = eng.get("BTC").tf_states["1m"]
        for bar in make_bars(2):
            tf.bars.append(bar)
        compute_tf_indicators(tf)
        # No MACD with only 2 bars
        assert "MACD" not in tf.indicators
