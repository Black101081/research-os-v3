import pytest
from multi_tf_state import MultiTFEngine, MultiTFSymbolState
from asset_tf_fitness import (
    is_fitness_ok, get_fitness, fitness_summary, BLOCK_THRESHOLD
)

# ── Fixtures ────────────────────────────────────────────────────────

ASSET_CFG = {
    "BTC": {"candle_intervals": ["1m", "5m", "15m", "1h"], "role": "anchor",
            "subscribe_l2book": True, "subscribe_active_asset_ctx": True},
    "ETH": {"candle_intervals": ["1m", "5m", "15m", "1h"], "role": "major",
            "subscribe_l2book": True, "subscribe_active_asset_ctx": True},
    "SOL": {"candle_intervals": ["5m", "15m", "1h"],       "role": "alt",
            "subscribe_l2book": False, "subscribe_active_asset_ctx": True},
}
MAX_BARS = {"1m": 500, "5m": 300, "15m": 200, "1h": 100}


@pytest.fixture
def engine():
    return MultiTFEngine(ASSET_CFG, MAX_BARS)


def _make_candle(symbol, interval, ts="2026-01-01T00:01:00+00:00", close=100.0):
    return {
        "candle": {
            "s": symbol, "i": interval,
            "t": ts, "o": close, "h": close+1, "l": close-1,
            "c": close, "v": 10.0, "n": 50,
        }
    }


# ── MultiTFEngine Tests ──────────────────────────────────────────────

def test_engine_initializes_all_tf_states(engine):
    btc = engine.get("BTC")
    assert btc is not None
    assert "1m" in btc.tf_states
    assert "5m" in btc.tf_states
    assert "15m" in btc.tf_states
    assert "1h" in btc.tf_states


def test_sol_has_no_1m_state(engine):
    sol = engine.get("SOL")
    assert "1m" not in sol.tf_states
    assert "5m" in sol.tf_states


def test_candle_routes_to_correct_tf_state(engine):
    msg = _make_candle("BTC", "5m", close=50000.0)
    engine.handle_candle(msg)
    btc = engine.get("BTC")
    assert len(btc.tf_states["5m"].bars) == 1
    assert btc.tf_states["5m"].bars[-1].close == 50000.0
    assert len(btc.tf_states["1m"].bars) == 0   # not touched


def test_candle_same_ts_replaces_not_appends(engine):
    msg = _make_candle("BTC", "5m", ts="2026-01-01T00:05:00+00:00", close=100.0)
    engine.handle_candle(msg)
    msg2 = _make_candle("BTC", "5m", ts="2026-01-01T00:05:00+00:00", close=101.0)
    engine.handle_candle(msg2)
    assert len(engine.get("BTC").tf_states["5m"].bars) == 1
    assert engine.get("BTC").tf_states["5m"].bars[-1].close == 101.0


def test_unknown_symbol_candle_ignored(engine):
    msg = _make_candle("DOGE", "5m", close=0.1)
    engine.handle_candle(msg)   # must not raise


def test_l2book_updates_bid_ask_levels(engine):
    data = {
        "coin": "BTC",
        "levels": [
            [{"px": "50000", "sz": "1.5"}, {"px": "49999", "sz": "2.0"}],
            [{"px": "50001", "sz": "0.8"}, {"px": "50002", "sz": "1.2"}],
        ]
    }
    engine.handle_l2book(data)
    btc = engine.get("BTC")
    assert len(btc.bid_levels) == 2
    assert btc.bid_levels[0] == (50000.0, 1.5)
    assert btc.ask_levels[0] == (50001.0, 0.8)


def test_active_asset_ctx_updates_funding_oi(engine):
    data = {
        "coin": "BTC",
        "ctx": {
            "funding": "0.0005",
            "openInterest": "12345.67",
            "markPx": "50100.0",
            "prevDayPx": "49000.0",
        }
    }
    engine.handle_active_asset_ctx(data)
    btc = engine.get("BTC")
    assert btc.funding_rate == pytest.approx(0.0005)
    assert btc.open_interest == pytest.approx(12345.67)


def test_htf_bias_neutral_when_insufficient_bars(engine):
    btc = engine.get("BTC")
    # No bars → neutral
    assert btc.htf_bias("15m") == "neutral"


def test_htf_bias_neutral_when_adx_low(engine):
    btc = engine.get("BTC")
    tf = btc.tf_states["15m"]
    # Fill 35 bars
    from multi_tf_state import TFBar
    for i in range(35):
        tf.bars.append(TFBar(ts=f"2026-01-01T{i:02d}:00:00+00:00",
                             open=100, high=101, low=99, close=100, volume=10))
    tf.indicators["adx_14"] = 15.0   # below threshold
    tf.indicators["MACD"] = 0.5
    tf.indicators["MACD_signal"] = 0.1
    tf.indicators["ema_spread_8_21"] = 0.01
    tf.indicators["rsi_14"] = 58.0
    assert btc.htf_bias("15m") == "neutral"   # ADX < 20 → neutral


def test_htf_bias_bullish_majority_vote(engine):
    from multi_tf_state import TFBar
    btc = engine.get("BTC")
    tf = btc.tf_states["15m"]
    for i in range(35):
        tf.bars.append(TFBar(ts=f"2026-01-01T{i:02d}:00:00+00:00",
                             open=100, high=101, low=99, close=100, volume=10))
    tf.indicators["adx_14"] = 28.0
    tf.indicators["MACD"] = 0.5
    tf.indicators["MACD_signal"] = 0.1
    tf.indicators["ema_spread_8_21"] = 0.02
    tf.indicators["rsi_14"] = 60.0
    assert btc.htf_bias("15m") == "bullish"


def test_mtf_alignment_all_bullish(engine):
    from multi_tf_state import TFBar
    btc = engine.get("BTC")
    for interval in ["5m", "15m", "1h"]:
        tf = btc.tf_states[interval]
        for i in range(35):
            tf.bars.append(TFBar(ts=f"2026-01-01T{i:02d}:00:00+00:00",
                                 open=100, high=101, low=99, close=100, volume=10))
        tf.indicators.update({"adx_14": 25.0, "MACD": 0.5, "MACD_signal": 0.1,
                               "ema_spread_8_21": 0.01, "rsi_14": 60.0})
    score = btc.mtf_alignment(["5m", "15m", "1h"])
    assert score == pytest.approx(1.0)


def test_orderbook_imbalance_bid_heavy(engine):
    btc = engine.get("BTC")
    btc.bid_levels = [(50000, 10.0), (49999, 5.0)]
    btc.ask_levels = [(50001, 3.0), (50002, 2.0)]
    imb = btc.orderbook_imbalance(levels=2)
    assert imb > 0   # bid pressure dominant


# ── Asset-TF Fitness Tests ───────────────────────────────────────────

def test_divergence_blocked_on_m1_anchor():
    assert is_fitness_ok("divergence", "anchor", "1m", 200) == False


def test_divergence_blocked_on_m1_alt():
    assert is_fitness_ok("divergence", "alt", "1m", 200) == False


def test_divergence_ok_btc_15m_sufficient_bars():
    assert is_fitness_ok("divergence", "anchor", "15m", 80) == True


def test_breakout_ok_btc_5m():
    assert is_fitness_ok("breakout", "anchor", "5m", 50) == True


def test_breakout_blocked_sol_m1():
    assert is_fitness_ok("breakout", "alt", "1m", 200) == False


def test_orderflow_blocked_sol_m1():
    assert is_fitness_ok("order_flow", "alt", "1m", 200) == False


def test_mean_reversion_blocked_btc_m1():
    assert is_fitness_ok("mean_reversion", "anchor", "1m", 200) == False


def test_continuation_blocked_sol_m1():
    assert is_fitness_ok("continuation", "alt", "1m", 200) == False


def test_insufficient_bars_blocks_even_if_score_ok():
    # breakout on BTC 5m needs min_bars=50; passing 30 → False
    assert is_fitness_ok("breakout", "anchor", "5m", 30) == False


def test_fitness_summary_returns_block_reason():
    result = fitness_summary("divergence", "anchor", "1m", 200)
    assert result["passed"] == False
    assert result["block_reason"] == "hard_block_score"
    assert result["score"] < BLOCK_THRESHOLD


def test_unknown_combination_blocked_by_default():
    assert is_fitness_ok("unknown_signal", "anchor", "2h", 200) == False


def test_funding_reversion_ok_btc():
    assert is_fitness_ok("funding_reversion", "anchor", "1m", 35) == True


def test_get_fitness_returns_reason():
    fit = get_fitness("divergence", "anchor", "1m")
    assert "reason" in fit
    assert "m1" in fit["reason"].lower() or "block" in fit["reason"].lower()
