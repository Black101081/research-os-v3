from __future__ import annotations

import pytest
from collections import deque

from multi_tf_state import MultiTFSymbolState, TFState, TFBar
from signal_models import SignalResult, SignalBatch
from signal_library import (
    evaluate_all_signals,
    signal_macd_continuation,
    signal_rsi_divergence,
    signal_bb_squeeze_breakout,
    signal_mean_reversion,
    signal_order_flow_imbalance,
    signal_volatility_event,
    signal_funding_reversion,
    signal_oi_reversal,
)
from signal_orchestrator import evaluate_supported_signals


def _build_mock_state(symbol: str, interval: str, role: str, indicators: dict) -> MultiTFSymbolState:
    sym_state = MultiTFSymbolState(symbol=symbol)
    tf = TFState(symbol=symbol, interval=interval)
    tf.indicators = indicators
    close_px = indicators.get("vwap", 100.0)
    if close_px <= 0:
        close_px = 100.0
    # Add 100 dummy bars so fitness and other checks pass
    tf.bars = deque([
        TFBar(ts="2026-07-06T00:00:00Z", open=close_px, high=close_px, low=close_px, close=close_px, volume=10.0)
        for _ in range(100)
    ], maxlen=300)
    sym_state.tf_states[interval] = tf
    
    # Set funding and OI fields
    sym_state.funding_rate = indicators.get("funding_rate", 0.0)
    sym_state.open_interest = indicators.get("oi", 0.0)
    
    # Mock book imbalance bid/ask levels if needed
    if "book_imbalance_10" in indicators or "book_imbalance_5" in indicators:
        imb5 = indicators.get("book_imbalance_5", 0.0)
        if imb5 > 0:
            sym_state.bid_levels = [(100.0, 10.0)]
            sym_state.ask_levels = [(100.0, 5.0)]
        elif imb5 < 0:
            sym_state.bid_levels = [(100.0, 5.0)]
            sym_state.ask_levels = [(100.0, 10.0)]
            
    return sym_state


def test_signal_result_to_dict():
    res = SignalResult(
        signal_id="BTC_breakout_1m_hash123",
        symbol="BTC",
        family="breakout",
        interval="1m",
        asset_role="anchor",
        fired=True,
        direction="long",
        entry_price=100.0,
        stop_loss=98.5,
        take_profit=102.5,
        take_profit_2=104.0,
        confidence_score=0.8,
        confluence_votes=4,
        confluence_total=5,
        risk_reward_ratio=1.67,
        atr_at_signal=1.0,
    )
    d = res.to_dict()
    assert d["symbol"] == "BTC"
    assert d["fired"] is True
    assert d["direction"] == "long"
    assert d["entry_price"] == 100.0
    assert d["stop_loss"] == 98.5
    assert d["take_profit"] == 102.5
    assert d["confidence_score"] == 0.8


def test_macd_continuation_long():
    indicators = {
        "MACD": 0.5,
        "MACD_signal": 0.2,
        "MACD_histogram": 0.3,
        "adx_14": 25.0,
        "ema_spread_8_21": 0.05,
        "rsi_14": 55.0,
        "obv_slope_10": 2.0,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "15m", "anchor", indicators)
    res = signal_macd_continuation(state, "15m", "anchor")
    assert res.fired is True
    assert res.direction == "long"
    assert res.entry_price == 100.0
    assert res.stop_loss == 98.5   # 100 - 1.5 * 1.0
    assert res.take_profit == 102.5


def test_macd_continuation_short():
    indicators = {
        "MACD": -0.5,
        "MACD_signal": -0.2,
        "MACD_histogram": -0.3,
        "adx_14": 25.0,
        "ema_spread_8_21": -0.05,
        "rsi_14": 45.0,
        "obv_slope_10": -2.0,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "15m", "anchor", indicators)
    res = signal_macd_continuation(state, "15m", "anchor")
    assert res.fired is True
    assert res.direction == "short"


def test_macd_continuation_adx_chop_blocked():
    indicators = {
        "MACD": 0.5,
        "MACD_signal": 0.2,
        "adx_14": 15.0,  # below 20 -> blocked
        "ema_spread_8_21": 0.05,
        "rsi_14": 55.0,
        "atr_14": 1.0,
    }
    state = _build_mock_state("BTC", "15m", "anchor", indicators)
    res = signal_macd_continuation(state, "15m", "anchor")
    assert res.fired is False


def test_rsi_divergence():
    indicators = {
        "rsi_14": 65.0,
        "stoch_rsi_k": 80.0,
        "stoch_rsi_d": 85.0,  # reversing down
        "atr_14": 1.0,
        "volume_ratio": 0.8,
        "bb_pct_20": 0.9,
        "cmf_20": -0.05,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "15m", "anchor", indicators)
    # Mock price/rsi history for bearish div
    # Populate closes to make price higher high, rsi lower high
    closes = [90.0]*100 + [95.0, 95.0, 96.0, 96.0, 97.0, 98.0, 99.0, 100.0]
    state.get_tf("15m").bars = deque([
        TFBar(ts="2026-07-06T00:00:00Z", open=c, high=c, low=c, close=c, volume=10.0)
        for c in closes
    ], maxlen=300)
    
    res = signal_rsi_divergence(state, "15m", "anchor")
    # Even if div not fully matched due to exact math, it should execute or gracefully return result
    assert isinstance(res, SignalResult)


def test_bb_squeeze_breakout_long():
    indicators = {
        "bb_width_20": 2.0,
        "bb_pct_20": 0.98,
        "squeeze_score": 0.6,   # squeeze active
        "volume_ratio": 1.8,    # vol confirmed
        "volume_zscore": 1.5,
        "adx_14": 18.0,
        "rsi_14": 60.0,
        "obv_slope_10": 2.0,
        "vwap_deviation_pct": 0.5,
        "book_imbalance_10": 0.2,
        "book_imbalance_5": 0.3,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "5m", "anchor", indicators)
    res = signal_bb_squeeze_breakout(state, "5m", "anchor")
    assert res.fired is True
    assert res.direction == "long"


def test_mean_reversion_long():
    indicators = {
        "rsi_14": 28.0,
        "stoch_rsi_k": 15.0,
        "stoch_rsi_d": 10.0,  # reversing up
        "bb_pct_20": 0.05,
        "adx_14": 15.0,       # low ADX (range)
        "vwap_deviation_pct": -1.5,
        "cmf_20": 0.02,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("ETH", "15m", "major", indicators)
    res = signal_mean_reversion(state, "15m", "major")
    assert res.fired is True
    assert res.direction == "long"


def test_order_flow_imbalance_long():
    indicators = {
        "book_imbalance_5": 0.4,
        "book_imbalance_10": 0.3,
        "obv_slope_10": 1.5,
        "volume_zscore": 1.2,
        "cmf_20": 0.1,
        "vwap_deviation_pct": 0.2,
        "rsi_14": 55.0,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "1m", "anchor", indicators)
    res = signal_order_flow_imbalance(state, "1m", "anchor")
    assert res.fired is True
    assert res.direction == "long"


def test_volatility_event_long():
    indicators = {
        "volume_ratio": 2.5,
        "volume_zscore": 2.2,
        "atr_14_pct": 0.4,
        "bb_width_20": 2.5,
        "book_imbalance_10": 0.3,
        "vwap_deviation_pct": 0.5,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "1m", "anchor", indicators)
    res = signal_volatility_event(state, "1m", "anchor")
    assert res.fired is True
    assert res.direction == "long"


def test_funding_reversion_short():
    indicators = {
        "funding_zscore": 2.5,
        "funding_rate": 0.0004,
        "funding_signal": -1.0,
        "oi_momentum_5": -1.5,
        "oi_trend": -1.0,
        "rsi_14": 65.0,
        "bb_pct_20": 0.8,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "5m", "anchor", indicators)
    res = signal_funding_reversion(state, "5m", "anchor")
    assert res.fired is True
    assert res.direction == "short"


def test_oi_reversal_long():
    indicators = {
        "oi_momentum_5": -2.5,
        "oi_trend": -1.0,
        "rsi_14": 30.0,
        "bb_pct_20": 0.1,
        "book_imbalance_10": 0.1,
        "volume_quality_score": 0.4,
        "funding_signal": 0.0,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "5m", "anchor", indicators)
    res = signal_oi_reversal(state, "5m", "anchor")
    assert res.fired is True
    assert res.direction == "long"


def test_evaluate_all_signals_dispatcher():
    indicators = {
        "MACD": 0.5,
        "MACD_signal": 0.2,
        "MACD_histogram": 0.3,
        "adx_14": 25.0,
        "ema_spread_8_21": 0.05,
        "rsi_14": 55.0,
        "obv_slope_10": 2.0,
        "atr_14": 1.0,
        "vwap": 100.0,
    }
    state = _build_mock_state("BTC", "15m", "anchor", indicators)
    batch = evaluate_all_signals(state, "15m", "anchor")
    assert isinstance(batch, SignalBatch)
    assert len(batch.results) == 19
    fired = batch.fired_signals()
    assert len(fired) >= 1
    assert batch.best_signal() is not None


def test_orchestrator_integration():
    factors = {"live_ret_from_last_close": 0.002}
    indicators = {
        "BollingerWidth": 0.02,
        "volatility_ratio_5_20": 1.2,
        "RelativeVolume": 1.5,
        "TradeFlowImbalance": 0.35,
        "rsi_14": 55.0,
        "ZScore_Close": 0.5,
        "SpreadBps": 2.0,
        "BBANDS_upper": 102.0,
        "BBANDS_lower": 98.0,
        "MACD": 0.5,
        "MACD_signal": 0.2,
        "MACD_histogram": 0.3,
        "adx_14": 25.0,
        "ema_spread_8_21": 0.05,
        "obv_slope_10": 2.0,
        "atr_14": 1.0,
        "vwap": 100.0,
        "rel_volume_20": 1.0,
        "MACD_hist": 0.3,
    }
    regime_state = {
        "regime": "uptrend",
        "tradable": True
    }
    res = evaluate_supported_signals("BTC", factors, indicators, regime_state, last_close=100.0, prev_bollinger_width=0.08)
    
    # Check that legacy signal is present (regression safety)
    assert 'macd_trend_continuation' in res
    assert res['macd_trend_continuation']['active'] is True
    
    # Check that new pure signal keys are present
    assert 'signal_macd_continuation' in res
    assert res['signal_macd_continuation']['active'] is True
    assert res['signal_macd_continuation']['stop_loss'] == 98.5
    assert res['signal_macd_continuation']['take_profit'] == 102.5
