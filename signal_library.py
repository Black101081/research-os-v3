from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

from asset_tf_fitness import is_fitness_ok
from multi_tf_state import MultiTFSymbolState, TFState
from signal_models import (
    DIRECTION_BOTH, DIRECTION_LONG, DIRECTION_SHORT,
    FAMILY_ORDER_FLOW, FAMILY_BREAKOUT, FAMILY_MEAN_REVERSION,
    FAMILY_CONTINUATION, FAMILY_DIVERGENCE, FAMILY_VOLATILITY_EVENT,
    FAMILY_FUNDING_REVERSION, FAMILY_OI_REVERSAL,
    FAMILY_MACD_CONTINUATION, FAMILY_EMA_PULLBACK_BUY, FAMILY_OBV_ACCUMULATION,
    FAMILY_HIGH_VOL_BREAKOUT, FAMILY_MOMENTUM_CHASING, FAMILY_VWAP_REVERSION_FADE,
    FAMILY_RANGE_BOUNDARY_FADE, FAMILY_LIQUIDITY_SWEEP, FAMILY_HFT_ORDER_FLOW,
    FAMILY_HIGH_VOL_BREAKDOWN, FAMILY_SHORT_MOMENTUM, FAMILY_OVERSOLD_BOUNCE,
    FAMILY_BEAR_TREND_CONTINUATION, FAMILY_EMA_PULLBACK_SELL, FAMILY_OBV_DISTRIBUTION,
    FAMILY_MEAN_REVERSION_SQUEEZE,
    SignalBatch, SignalResult,
)


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_signal_id(symbol: str, family: str, interval: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    raw = f"{symbol}_{family}_{interval}_{ts}"
    return raw + "_" + hashlib.md5(raw.encode()).hexdigest()[:6]


def _no_signal(symbol: str, family: str, interval: str,
               asset_role: str, reason: str = "") -> SignalResult:
    return SignalResult(
        signal_id=_make_signal_id(symbol, family, interval),
        symbol=symbol, family=family, interval=interval,
        asset_role=asset_role, fired=False,
        direction=DIRECTION_BOTH,
        notes=[reason] if reason else [],
    )


def _calc_levels(entry: float, atr: float, direction: str,
                 sl_mult: float = 1.5, tp_mult: float = 2.5
                 ) -> tuple:
    """
    Returns (stop_loss, take_profit, take_profit_2, rr_ratio, invalidation).
    sl_mult / tp_mult in ATR units.
    """
    if atr <= 0 or entry <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    if direction == DIRECTION_LONG:
        sl   = entry - sl_mult * atr
        tp   = entry + tp_mult * atr
        tp2  = entry + 4.0 * atr
        inv  = entry - 2.0 * atr
    else:
        sl   = entry + sl_mult * atr
        tp   = entry - tp_mult * atr
        tp2  = entry - 4.0 * atr
        inv  = entry + 2.0 * atr
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0.0
    return sl, tp, tp2, rr, inv


def _get_ind(tf: TFState) -> Dict:
    return tf.indicators if tf else {}


def _snapshot(ind: Dict, keys: List[str]) -> Dict:
    return {k: round(v, 6) for k, v in ind.items() if k in keys}


# ─────────────────────────────────────────────────────────────────────
# GROUP A: BULLISH LOW-NORMAL VOLATILITY
# ─────────────────────────────────────────────────────────────────────

def signal_macd_continuation(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_MACD_CONTINUATION
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_CONTINUATION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, family, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    macd      = ind.get("MACD", 0.0)
    macd_sig  = ind.get("MACD_signal", 0.0)
    macd_hist = ind.get("MACD_histogram", 0.0)
    adx       = ind.get("adx_14", 0.0)
    ema_sp    = ind.get("ema_spread_8_21", 0.0)
    rsi       = ind.get("rsi_14", 50.0)
    obv_sl    = ind.get("obv_slope_10", 0.0)
    atr       = ind.get("atr_14", 0.0)
    close     = tf.bars[-1].close if tf.bars else 0.0

    if adx < 20.0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "adx_low_chop_blocked")

    direction = DIRECTION_LONG if ema_sp > 0.01 else (DIRECTION_SHORT if ema_sp < -0.01 else None)
    if direction is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_trend")

    if "cvd_slope_20" in ind:
        cvd_slope = ind["cvd_slope_20"]
        if direction == DIRECTION_LONG and cvd_slope <= 0.0:
            return _no_signal(sym_state.symbol, family, interval, asset_role, "cvd_slope_bearish_blocked")
        if direction == DIRECTION_SHORT and cvd_slope >= 0.0:
            return _no_signal(sym_state.symbol, family, interval, asset_role, "cvd_slope_bullish_blocked")

    # Confluence check
    if direction == DIRECTION_LONG:
        votes_list = [
            macd > macd_sig,
            macd_hist > 0,
            rsi > 50 and rsi < 68,
            obv_sl > 0,
        ]
    else:
        votes_list = [
            macd < macd_sig,
            macd_hist < 0,
            rsi < 50 and rsi > 32,
            obv_sl < 0,
        ]
    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 3 or close == 0 or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, f"low_votes={votes}")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.5, tp_mult=2.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=votes/total, confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"votes={votes}/{total}", f"adx={adx:.1f}"],
        indicators_snapshot=_snapshot(ind, ["MACD", "MACD_signal", "rsi_14", "adx_14"])
    )


def signal_ema_pullback_buy(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_EMA_PULLBACK_BUY
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_CONTINUATION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, family, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    ema_20 = ind.get("ema_20", 0.0)
    ema_50 = ind.get("ema_50", 0.0)
    ema_sp = ind.get("ema_spread_8_21", 0.0)
    atr = ind.get("atr_14", 0.0)

    # Bull trend EMA spread check
    if ema_sp < 0.005 or ema_20 <= ema_50:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "not_in_uptrend")

    # Pullback check: close is near EMA 20 or EMA 50
    pullback = (close > ema_50) and (close <= ema_20 * 1.005)
    if not pullback:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_pullback")

    # Bullish pattern check
    has_pattern = (ind.get("pattern_hammer", 0.0) > 0 or 
                   ind.get("pattern_bull_engulfing", 0.0) > 0 or 
                   ind.get("pattern_pinbar", 0.0) > 0)
    if not has_pattern:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_candlestick_reversal")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_LONG, sl_mult=1.2, tp_mult=2.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_LONG, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.80, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["ema_pullback_detected", "reversal_pattern_confirmed"],
        indicators_snapshot=_snapshot(ind, ["ema_20", "ema_50", "ema_spread_8_21"])
    )


def signal_obv_accumulation_breakout(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_OBV_ACCUMULATION
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    bb_pct = ind.get("bb_pct_20", 0.5)
    obv_sl = ind.get("obv_slope_10", 0.0)
    vol_ratio = ind.get("volume_ratio", 1.0)
    atr = ind.get("atr_14", 0.0)

    # OBV accumulation: OBV slope strongly positive while price is consolidated near Upper BB
    accumulation = (obv_sl > 5.0) and (bb_pct > 0.75) and (vol_ratio > 1.2)
    if not accumulation or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_obv_accumulation")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_LONG, sl_mult=1.5, tp_mult=3.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_LONG, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.78, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["obv_accumulation_breakout_confirmed"],
        indicators_snapshot=_snapshot(ind, ["bb_pct_20", "obv_slope_10", "volume_ratio"])
    )


# ─────────────────────────────────────────────────────────────────────
# GROUP B: BULLISH HIGH VOLATILITY
# ─────────────────────────────────────────────────────────────────────

def signal_high_vol_breakout(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_HIGH_VOL_BREAKOUT
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    kc_upper = ind.get("kc_upper", 0.0)
    park_vol = ind.get("parkinson_volatility_20", 0.0)
    vol_ratio = ind.get("volume_ratio", 1.0)
    atr = ind.get("atr_14", 0.0)

    # Volatility breakout: price above upper Keltner channel, high Parkinson vol, high volume
    fired = (close > kc_upper) and (park_vol > 0.018) and (vol_ratio > 1.4)
    if not fired or atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_vol_breakout")

    if "cvd_slope_20" in ind:
        cvd_slope = ind["cvd_slope_20"]
        if cvd_slope <= 0.0:
            return _no_signal(sym_state.symbol, family, interval, asset_role, "cvd_slope_bearish_blocked")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_LONG, sl_mult=2.0, tp_mult=3.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_LONG, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.85, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["high_volatility_breakout_confirmed"],
        indicators_snapshot=_snapshot(ind, ["kc_upper", "parkinson_volatility_20", "volume_ratio"])
    )


def signal_momentum_chasing(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_MOMENTUM_CHASING
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    adx = ind.get("adx_14", 0.0)
    st_dir = ind.get("supertrend_direction", 0.0)
    rsi = ind.get("rsi_14", 50.0)
    atr = ind.get("atr_14", 0.0)

    # Momentum chasing: SuperTrend is positive, ADX > 28, RSI is high but not yet exhausted
    fired = (st_dir == 1.0) and (adx > 28.0) and (rsi > 58.0 and rsi < 78.0)
    if not fired or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_momentum_chase")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_LONG, sl_mult=2.2, tp_mult=3.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_LONG, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.76, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["momentum_chase_confirmed"],
        indicators_snapshot=_snapshot(ind, ["adx_14", "supertrend_direction", "rsi_14"])
    )


def signal_vwap_reversion_fade(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_VWAP_REVERSION_FADE
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    vwap_dev = ind.get("vwap_deviation_pct", 0.0)
    bb_pct = ind.get("bb_pct_20", 0.5)
    rsi = ind.get("rsi_14", 50.0)
    atr = ind.get("atr_14", 0.0)

    # Fade extreme extension: price way above VWAP, overbought RSI, price above Upper BB
    # We trade SHORT (fading)
    fired = (vwap_dev > 1.8) and (bb_pct > 0.95) and (rsi > 75.0)
    if not fired or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_reversion_extreme")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_SHORT, sl_mult=1.5, tp_mult=2.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_SHORT, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.82, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["vwap_deviation_fade_short"],
        indicators_snapshot=_snapshot(ind, ["vwap_deviation_pct", "bb_pct_20", "rsi_14"])
    )


# ─────────────────────────────────────────────────────────────────────
# GROUP C: SIDEWAYS HIGH VOLATILITY
# ─────────────────────────────────────────────────────────────────────

def signal_range_boundary_fade(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_RANGE_BOUNDARY_FADE
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    bb_pct = ind.get("bb_pct_20", 0.5)
    stoch_k = ind.get("stoch_k", 50.0)
    stoch_d = ind.get("stoch_d", 50.0)
    atr = ind.get("atr_14", 0.0)

    # Buy at support (Lower BB + stochastic crossover up), sell at resistance (Upper BB + crossover down)
    long_fade = (bb_pct < 0.10) and (stoch_k < 20.0) and (stoch_k > stoch_d)
    short_fade = (bb_pct > 0.90) and (stoch_k > 80.0) and (stoch_k < stoch_d)

    if not long_fade and not short_fade:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_range_fade_setup")

    direction = DIRECTION_LONG if long_fade else DIRECTION_SHORT
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.0, tp_mult=1.8)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.74, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"range_boundary_fade_{direction}"],
        indicators_snapshot=_snapshot(ind, ["bb_pct_20", "stoch_k", "stoch_d"])
    )


def signal_liquidity_sweep_hunt(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_LIQUIDITY_SWEEP
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    vah = ind.get("vol_profile_vah", 0.0)
    val = ind.get("vol_profile_val", 0.0)
    atr = ind.get("atr_14", 0.0)

    if val == 0 or vah == 0 or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_value_area")

    # Sweep hunt: price briefly crosses outside VAH/VAL, followed by a pinbar or engulfing candle reversing back inside
    long_sweep = (close > val) and (tf.bars[-1].low < val) and (ind.get("pattern_pinbar", 0.0) > 0 or ind.get("pattern_hammer", 0.0) > 0)
    short_sweep = (close < vah) and (tf.bars[-1].high > vah) and (ind.get("pattern_pinbar", 0.0) > 0 or ind.get("pattern_shooting_star", 0.0) > 0)

    if not long_sweep and not short_sweep:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_sweep_detected")

    direction = DIRECTION_LONG if long_sweep else DIRECTION_SHORT
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.0, tp_mult=2.0)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.80, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"liquidity_sweep_{direction}_confirmed"],
        indicators_snapshot=_snapshot(ind, ["vol_profile_vah", "vol_profile_val"])
    )


def signal_hft_order_flow_momentum(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_HFT_ORDER_FLOW
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    decayed_tfi = ind.get("decayed_flow_imbalance_20")
    if decayed_tfi is None:
        decayed_tfi = ind.get("book_imbalance_5", 0.0)
    vol_zscore = ind.get("volume_zscore", 0.0)
    atr = ind.get("atr_14", 0.0)

    # HFT momentum: strong trade flow imbalance (>0.35) confirmed by elevated volume z-score
    fired = abs(decayed_tfi) >= 0.35 and vol_zscore > 1.2
    if not fired or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_hft_imbalance")

    direction = DIRECTION_LONG if decayed_tfi > 0 else DIRECTION_SHORT
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=0.8, tp_mult=1.5)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.75, confluence_votes=2, confluence_total=2,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["hft_order_flow_signal_confirmed"],
        indicators_snapshot=_snapshot(ind, ["book_imbalance_5", "volume_zscore"])
    )


# ─────────────────────────────────────────────────────────────────────
# GROUP D: BEARISH HIGH VOLATILITY
# ─────────────────────────────────────────────────────────────────────

def signal_high_vol_breakdown(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_HIGH_VOL_BREAKDOWN
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    kc_lower = ind.get("kc_lower", 0.0)
    park_vol = ind.get("parkinson_volatility_20", 0.0)
    vol_ratio = ind.get("volume_ratio", 1.0)
    atr = ind.get("atr_14", 0.0)

    # Vol breakdown: price below lower Keltner channel, high Parkinson vol, high volume
    fired = (close < kc_lower) and (park_vol > 0.018) and (vol_ratio > 1.4)
    if not fired or atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_vol_breakdown")

    if "cvd_slope_20" in ind:
        cvd_slope = ind["cvd_slope_20"]
        if cvd_slope >= 0.0:
            return _no_signal(sym_state.symbol, family, interval, asset_role, "cvd_slope_bullish_blocked")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_SHORT, sl_mult=2.0, tp_mult=3.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_SHORT, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.85, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["high_volatility_breakdown_confirmed"],
        indicators_snapshot=_snapshot(ind, ["kc_lower", "parkinson_volatility_20", "volume_ratio"])
    )


def signal_short_momentum_chase(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_SHORT_MOMENTUM
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    adx = ind.get("adx_14", 0.0)
    st_dir = ind.get("supertrend_direction", 0.0)
    rsi = ind.get("rsi_14", 50.0)
    atr = ind.get("atr_14", 0.0)

    # Short momentum chasing: SuperTrend is negative, ADX > 28, RSI is low but not yet oversold
    fired = (st_dir == -1.0) and (adx > 28.0) and (rsi < 42.0 and rsi > 22.0)
    if not fired or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_short_momentum_chase")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_SHORT, sl_mult=2.2, tp_mult=3.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_SHORT, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.76, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["short_momentum_chase_confirmed"],
        indicators_snapshot=_snapshot(ind, ["adx_14", "supertrend_direction", "rsi_14"])
    )


def signal_oversold_bounce(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_OVERSOLD_BOUNCE
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    vwap_dev = ind.get("vwap_deviation_pct", 0.0)
    rsi = ind.get("rsi_14", 50.0)
    atr = ind.get("atr_14", 0.0)

    # Oversold bounce fade: price extremely far below VWAP, RSI under 20, bullish pinbar or hammer present
    # We trade LONG (bounce buy)
    fired = (vwap_dev < -2.2) and (rsi < 20.0) and (ind.get("pattern_pinbar", 0.0) > 0 or ind.get("pattern_hammer", 0.0) > 0)
    if not fired or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_oversold_bounce")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_LONG, sl_mult=1.5, tp_mult=2.2)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_LONG, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.82, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["oversold_bounce_long_confirmed"],
        indicators_snapshot=_snapshot(ind, ["vwap_deviation_pct", "rsi_14"])
    )


# ─────────────────────────────────────────────────────────────────────
# GROUP E: BEARISH LOW-NORMAL VOLATILITY
# ─────────────────────────────────────────────────────────────────────

def signal_bearish_trend_continuation(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_BEAR_TREND_CONTINUATION
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_CONTINUATION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, family, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    macd      = ind.get("MACD", 0.0)
    macd_sig  = ind.get("MACD_signal", 0.0)
    macd_hist = ind.get("MACD_histogram", 0.0)
    adx       = ind.get("adx_14", 0.0)
    ema_sp    = ind.get("ema_spread_8_21", 0.0)
    rsi       = ind.get("rsi_14", 50.0)
    obv_sl    = ind.get("obv_slope_10", 0.0)
    atr       = ind.get("atr_14", 0.0)
    close     = tf.bars[-1].close if tf.bars else 0.0

    if ema_sp >= -0.01:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_bear_trend")

    # SHORT confluence check
    short_votes = [
        macd < macd_sig,
        macd_hist < 0,
        rsi < 50 and rsi > 32,
        obv_sl < 0,
    ]
    votes = sum(short_votes)
    total = len(short_votes)

    if votes < 3 or close == 0 or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, f"low_votes={votes}")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_SHORT, sl_mult=1.5, tp_mult=2.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_SHORT, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=votes/total, confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"votes={votes}/{total}", f"adx={adx:.1f}"],
        indicators_snapshot=_snapshot(ind, ["MACD", "MACD_signal", "rsi_14", "adx_14"])
    )


def signal_ema_pullback_sell(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_EMA_PULLBACK_SELL
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_CONTINUATION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, family, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    ema_20 = ind.get("ema_20", 0.0)
    ema_50 = ind.get("ema_50", 0.0)
    ema_sp = ind.get("ema_spread_8_21", 0.0)
    atr = ind.get("atr_14", 0.0)

    # Bear trend EMA spread check
    if ema_sp > -0.005 or ema_20 >= ema_50:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "not_in_downtrend")

    # Pullback check: close is near EMA 20 or EMA 50
    pullback = (close < ema_50) and (close >= ema_20 * 0.995)
    if not pullback:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_pullback")

    # Bearish pattern check
    has_pattern = (ind.get("pattern_shooting_star", 0.0) > 0 or 
                   ind.get("pattern_bear_engulfing", 0.0) > 0 or 
                   ind.get("pattern_pinbar", 0.0) > 0)
    if not has_pattern:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_candlestick_reversal")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_SHORT, sl_mult=1.2, tp_mult=2.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_SHORT, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.80, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["ema_pullback_detected", "reversal_pattern_confirmed"],
        indicators_snapshot=_snapshot(ind, ["ema_20", "ema_50", "ema_spread_8_21"])
    )


def signal_obv_distribution_breakdown(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_OBV_DISTRIBUTION
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    bb_pct = ind.get("bb_pct_20", 0.5)
    obv_sl = ind.get("obv_slope_10", 0.0)
    vol_ratio = ind.get("volume_ratio", 1.0)
    atr = ind.get("atr_14", 0.0)

    # OBV distribution: OBV slope strongly negative while price is consolidated near Lower BB
    distribution = (obv_sl < -5.0) and (bb_pct < 0.25) and (vol_ratio > 1.2)
    if not distribution or atr == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_obv_distribution")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, DIRECTION_SHORT, sl_mult=1.5, tp_mult=3.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=DIRECTION_SHORT, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.78, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=["obv_distribution_breakdown_confirmed"],
        indicators_snapshot=_snapshot(ind, ["bb_pct_20", "obv_slope_10", "volume_ratio"])
    )


# ─────────────────────────────────────────────────────────────────────
# GROUP F: SIDEWAYS LOW-NORMAL VOLATILITY
# ─────────────────────────────────────────────────────────────────────

def signal_mean_reversion_squeeze(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_MEAN_REVERSION_SQUEEZE
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    close = tf.bars[-1].close if tf.bars else 0.0
    bb_pct = ind.get("bb_pct_20", 0.5)
    stoch_k = ind.get("stoch_k", 50.0)
    stoch_d = ind.get("stoch_d", 50.0)
    sq_score = ind.get("squeeze_score", 0.0)
    atr = ind.get("atr_14", 0.0)

    # Squeeze reversion: Bollinger bands tight (squeeze_score > 0.70) + price borders + stochastic reversal
    long_revert = (sq_score > 0.70) and (bb_pct < 0.15) and (stoch_k < 20.0) and (stoch_k > stoch_d)
    short_revert = (sq_score > 0.70) and (bb_pct > 0.85) and (stoch_k > 80.0) and (stoch_k < stoch_d)

    if not long_revert and not short_revert:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_squeeze_reversion")

    direction = DIRECTION_LONG if long_revert else DIRECTION_SHORT
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.0, tp_mult=1.5)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=0.80, confluence_votes=3, confluence_total=3,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"squeeze_reversion_{direction}_confirmed"],
        indicators_snapshot=_snapshot(ind, ["squeeze_score", "bb_pct_20", "stoch_k"])
    )


def signal_funding_reversion(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_FUNDING_REVERSION
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_FUNDING_REVERSION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, family, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    funding_z  = ind.get("funding_zscore", 0.0)
    funding_r  = ind.get("funding_rate", 0.0)
    funding_s  = ind.get("funding_signal", 0.0)
    oi_mom     = ind.get("oi_momentum_5", 0.0)
    oi_trend   = ind.get("oi_trend", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    bb_pct     = ind.get("bb_pct_20", 0.5)
    atr        = ind.get("atr_14", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0

    if abs(funding_z) < 2.0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, f"funding_z_not_extreme={funding_z:.2f}")

    direction = DIRECTION_SHORT if funding_z > 2.0 else DIRECTION_LONG
    if direction == DIRECTION_SHORT:
        votes_list = [
            funding_z > 2.0,
            funding_r > 0.0003,
            oi_mom < 0,
            rsi > 60,
            bb_pct > 0.7,
            oi_trend <= 0,
        ]
    else:
        votes_list = [
            funding_z < -2.0,
            funding_r < -0.0001,
            oi_mom < 0,
            rsi < 40,
            bb_pct < 0.3,
            oi_trend <= 0,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 3 or atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, f"low_confluence={votes}/{total}")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.5, tp_mult=2.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=votes/total, confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"funding_reversion_{direction}_confirmed"],
        indicators_snapshot=_snapshot(ind, ["funding_zscore", "funding_rate", "oi_momentum_5"])
    )


def signal_oi_reversal(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    family = FAMILY_OI_REVERSAL
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_OI_REVERSAL, asset_role, interval, n):
        return _no_signal(sym_state.symbol, family, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    oi_mom     = ind.get("oi_momentum_5", 0.0)
    oi_trend   = ind.get("oi_trend", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    bb_pct     = ind.get("bb_pct_20", 0.5)
    atr        = ind.get("atr_14", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0
    funding_s  = ind.get("funding_signal", 0.0)
    book_imb   = ind.get("book_imbalance_10", 0.0)

    if abs(oi_mom) < 1.0 and oi_trend == 0.0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, f"oi_not_reversing={oi_mom:.2f}")

    long_trigger  = bb_pct < 0.25 and oi_mom < -1.0
    short_trigger = bb_pct > 0.75 and oi_mom < -1.0

    if not long_trigger and not short_trigger:
        return _no_signal(sym_state.symbol, family, interval, asset_role, "no_oi_extreme")

    direction = DIRECTION_LONG if long_trigger else DIRECTION_SHORT
    if direction == DIRECTION_LONG:
        votes_list = [
            bb_pct < 0.25,
            oi_mom < -1.0,
            rsi < 45,
            book_imb > 0.05,
            funding_s >= 0.0,
        ]
    else:
        votes_list = [
            bb_pct > 0.75,
            oi_mom < -1.0,
            rsi > 55,
            book_imb < -0.05,
            funding_s <= 0.0,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 3 or atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, family, interval, asset_role, f"low_confluence={votes}/{total}")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.5, tp_mult=2.5)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, family, interval),
        symbol=sym_state.symbol, family=family, interval=interval, asset_role=asset_role,
        fired=True, direction=direction, entry_price=close, stop_loss=sl, take_profit=tp, take_profit_2=tp2,
        confidence_score=votes/total, confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr, invalidation_price=inv,
        notes=[f"oi_reversal_{direction}_confirmed"],
        indicators_snapshot=_snapshot(ind, ["oi_momentum_5", "oi_trend", "bb_pct_20"])
    )


# ─────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────

def evaluate_all_signals(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalBatch:
    """Evaluate all 19 signals for a given symbol, timeframe, and role."""
    results = [
        # Group A
        signal_macd_continuation(sym_state, interval, asset_role),
        signal_ema_pullback_buy(sym_state, interval, asset_role),
        signal_obv_accumulation_breakout(sym_state, interval, asset_role),
        # Group B
        signal_high_vol_breakout(sym_state, interval, asset_role),
        signal_momentum_chasing(sym_state, interval, asset_role),
        signal_vwap_reversion_fade(sym_state, interval, asset_role),
        # Group C
        signal_range_boundary_fade(sym_state, interval, asset_role),
        signal_liquidity_sweep_hunt(sym_state, interval, asset_role),
        signal_hft_order_flow_momentum(sym_state, interval, asset_role),
        # Group D
        signal_high_vol_breakdown(sym_state, interval, asset_role),
        signal_short_momentum_chase(sym_state, interval, asset_role),
        signal_oversold_bounce(sym_state, interval, asset_role),
        # Group E
        signal_bearish_trend_continuation(sym_state, interval, asset_role),
        signal_ema_pullback_sell(sym_state, interval, asset_role),
        signal_obv_distribution_breakdown(sym_state, interval, asset_role),
        # Group F
        signal_mean_reversion_squeeze(sym_state, interval, asset_role),
        signal_funding_reversion(sym_state, interval, asset_role),
        signal_oi_reversal(sym_state, interval, asset_role),
        
        # Divergence Family
        signal_cvd_divergence(sym_state, interval, asset_role),
    ]

    # Apply Multi-Timeframe Trend Gating
    htf = None
    if interval == "1m":
        htf = sym_state.get_tf("15m")
    elif interval == "5m":
        htf = sym_state.get_tf("15m") or sym_state.get_tf("1h")
    elif interval == "15m":
        htf = sym_state.get_tf("1h")
        
    htf_trend = None
    if htf is not None:
        ema_spread = htf.indicators.get("ema_spread_8_21")
        if ema_spread is not None:
            if ema_spread > 0.0:
                htf_trend = DIRECTION_LONG
            elif ema_spread < 0.0:
                htf_trend = DIRECTION_SHORT

    if htf_trend is not None:
        for r in results:
            if r.fired:
                if r.direction == DIRECTION_BOTH:
                    r.direction = htf_trend
                    r.notes.append(f"direction_gated_to_{htf_trend}")
                elif r.direction != htf_trend:
                    # Block signal
                    r.fired = False
                    r.invalidation_reason = f"mtf_trend_conflict_{htf_trend}"
                    r.notes.append(f"blocked_by_mtf_trend_{htf_trend}")

    return SignalBatch(
        symbol=sym_state.symbol,
        interval=interval,
        results=results,
    )


# ─────────────────────────────────────────────────────────────────────
# LEGACY BACKWARD-COMPATIBLE SIGNAL FUNCTIONS
# ─────────────────────────────────────────────────────────────────────

def signal_rsi_divergence(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_DIVERGENCE, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    rsi        = ind.get("rsi_14", 50.0)
    stoch_k    = ind.get("stoch_rsi_k", 50.0)
    stoch_d    = ind.get("stoch_rsi_d", 50.0)
    atr        = ind.get("atr_14", 0.0)
    vol_ratio  = ind.get("volume_ratio", 1.0)
    bb_pct     = ind.get("bb_pct_20", 0.5)
    cmf        = ind.get("cmf_20", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0
    vol_q      = ind.get("volume_quality_score", 0.0)

    if n < 20 or atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "insufficient_context")

    closes = tf.closes()
    rsi_vals = []
    from factor_math import calc_rsi as _calc_rsi
    for i in range(max(15, n - 20), n + 1):
        rsi_vals.append(_calc_rsi(closes[:i], 14))

    if len(rsi_vals) < 5:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "rsi_series_short")

    recent_closes = closes[-15:]
    recent_rsi    = rsi_vals[-15:]

    price_high1 = max(recent_closes[:8])
    price_high2 = max(recent_closes[7:])
    rsi_high1   = max(recent_rsi[:8])
    rsi_high2   = max(recent_rsi[7:])

    price_low1  = min(recent_closes[:8])
    price_low2  = min(recent_closes[7:])
    rsi_low1    = min(recent_rsi[:8])
    rsi_low2    = min(recent_rsi[7:])

    bearish_div = (price_high2 > price_high1 * 1.001 and
                   rsi_high2   < rsi_high1   - 2.0 and
                   rsi >= 55)

    bullish_div = (price_low2  < price_low1  * 0.999 and
                   rsi_low2    > rsi_low1    + 2.0 and
                   rsi <= 45)

    if not bearish_div and not bullish_div:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "no_divergence_detected")

    direction = DIRECTION_SHORT if bearish_div else DIRECTION_LONG

    if direction == DIRECTION_SHORT:
        votes_list = [
            bearish_div,
            stoch_k > 75,
            stoch_k < stoch_d,
            vol_ratio < 0.9,
            bb_pct > 0.85,
            cmf < 0.0,
        ]
    else:
        votes_list = [
            bullish_div,
            stoch_k < 25,
            stoch_k > stoch_d,
            vol_ratio < 0.9,
            bb_pct < 0.15,
            cmf > 0.0,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 3:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, f"low_confluence={votes}/{total}")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.2, tp_mult=2.0)
    conf = votes / total

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_DIVERGENCE, interval),
        symbol=sym_state.symbol, family=FAMILY_DIVERGENCE,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        invalidation_price=inv,
        invalidation_reason=f"divergence_void_above_{inv:.2f}",
        indicators_snapshot=_snapshot(ind, [
            "rsi_14", "stoch_rsi_k", "stoch_rsi_d",
            "bb_pct_20", "cmf_20", "volume_ratio", "atr_14",
        ]),
        notes=[f"rsi={rsi:.1f}", f"votes={votes}/{total}"],
    )


def signal_bb_squeeze_breakout(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_BREAKOUT, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT, interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    bb_pct     = ind.get("bb_pct_20", 0.5)
    squeeze_sc = ind.get("squeeze_score", 0.0)
    vol_ratio  = ind.get("volume_ratio", 1.0)
    vol_zscore = ind.get("volume_zscore", 0.0)
    adx        = ind.get("adx_14", 0.0)
    atr        = ind.get("atr_14", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    close      = tf.bars[-1].close if tf.bars else 0.0

    # Ensure squeeze score is ready or fallback
    if squeeze_sc < 0.4:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT, interval, asset_role, f"no_squeeze={squeeze_sc:.2f}")

    if bb_pct > 0.95:
        direction = DIRECTION_LONG
    elif bb_pct < 0.05:
        direction = DIRECTION_SHORT
    else:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT, interval, asset_role, f"price_not_at_band={bb_pct:.2f}")

    if vol_ratio < 1.4:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT, interval, asset_role, f"no_volume={vol_ratio:.2f}")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=1.0, tp_mult=2.0)
    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_BREAKOUT, interval),
        symbol=sym_state.symbol, family=FAMILY_BREAKOUT,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=0.8,
        confluence_votes=4, confluence_total=5,
        risk_reward_ratio=rr, atr_at_signal=atr,
        invalidation_price=inv,
        indicators_snapshot=_snapshot(ind, ["bb_pct_20", "squeeze_score", "volume_ratio", "atr_14"]),
        notes=[f"squeeze={squeeze_sc:.2f}", f"direction={direction}"],
    )


_OPTUNA_PARAMS_CACHE = None

def _get_optuna_params(symbol: str, interval: str) -> dict:
    global _OPTUNA_PARAMS_CACHE
    if _OPTUNA_PARAMS_CACHE is None:
        path = Path("runtime/optuna_parameter_matrix.json")
        if path.exists():
            try:
                _OPTUNA_PARAMS_CACHE = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                _OPTUNA_PARAMS_CACHE = {}
        else:
            _OPTUNA_PARAMS_CACHE = {}
            
    defaults = {
        "adx_threshold": 28.0,
        "atr_multiplier": 2.0,
        "rsi_period": 14,
        "rsi_lower": 35.0,
        "rsi_upper": 65.0
    }
    
    sym_data = _OPTUNA_PARAMS_CACHE.get(symbol, {})
    tf_data = sym_data.get(interval, {})
    return {
        "adx_threshold": tf_data.get("adx_threshold", defaults["adx_threshold"]),
        "atr_multiplier": tf_data.get("atr_multiplier", defaults["atr_multiplier"]),
        "rsi_period": int(tf_data.get("rsi_period", defaults["rsi_period"])),
        "rsi_lower": tf_data.get("rsi_lower", defaults["rsi_lower"]),
        "rsi_upper": tf_data.get("rsi_upper", defaults["rsi_upper"])
    }

def signal_mean_reversion(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION, interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_MEAN_REVERSION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION, interval, asset_role, "fitness_blocked")

    # Load dynamic parameters
    params = _get_optuna_params(sym_state.symbol, interval)
    adx_threshold = params["adx_threshold"]
    atr_multiplier = params["atr_multiplier"]
    rsi_period = params["rsi_period"]
    rsi_lower = params["rsi_lower"]
    rsi_upper = params["rsi_upper"]

    ind = _get_ind(tf)
    
    # Recalculate RSI dynamically if rsi_period is different from 14 and we have enough non-flat bars
    if rsi_period == 14 or len(tf.bars) < rsi_period + 1:
        rsi = ind.get("rsi_14", 50.0)
    else:
        closes = [b.close for b in tf.bars]
        if max(closes) == min(closes):
            rsi = ind.get("rsi_14", 50.0)
        else:
            import factor_math as fm
            rsi = fm.calc_rsi(closes, period=rsi_period)

    bb_pct    = ind.get("bb_pct_20", 0.5)
    adx       = ind.get("adx_14", 0.0)
    vwap_dev  = ind.get("vwap_deviation_pct", 0.0)
    atr       = ind.get("atr_14", 0.0)
    close     = tf.bars[-1].close if tf.bars else 0.0

    if adx > adx_threshold:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION, interval, asset_role, f"trending_market_adx={adx:.1f}_gt_{adx_threshold:.1f}")

    long_extreme  = bb_pct < 0.10 and rsi < rsi_lower and vwap_dev < -1.0
    short_extreme = bb_pct > 0.90 and rsi > rsi_upper and vwap_dev > 1.0

    if not long_extreme and not short_extreme:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION, interval, asset_role, "no_extreme")

    direction = DIRECTION_LONG if long_extreme else DIRECTION_SHORT
    # Apply optimized atr_multiplier to stop loss calculation
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=atr_multiplier, tp_mult=1.5)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_MEAN_REVERSION, interval),
        symbol=sym_state.symbol, family=FAMILY_MEAN_REVERSION,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=0.75,
        confluence_votes=3, confluence_total=4,
        risk_reward_ratio=rr, atr_at_signal=atr,
        invalidation_price=inv,
        indicators_snapshot=_snapshot(ind, ["rsi_14", "bb_pct_20", "vwap_deviation_pct", "atr_14"]),
        notes=[f"vwap_dev={vwap_dev:.2f}%", f"direction={direction}"],
    )


def signal_order_flow_imbalance(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    book_imb5 = ind.get("book_imbalance_5", 0.0)
    atr       = ind.get("atr_14", 0.0)
    close     = tf.bars[-1].close if tf.bars else 0.0

    if abs(book_imb5) < 0.25:
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW, interval, asset_role, "low_imbalance")

    direction = DIRECTION_LONG if book_imb5 > 0.0 else DIRECTION_SHORT
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=0.8, tp_mult=1.5)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_ORDER_FLOW, interval),
        symbol=sym_state.symbol, family=FAMILY_ORDER_FLOW,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=0.8,
        confluence_votes=4, confluence_total=5,
        risk_reward_ratio=rr, atr_at_signal=atr,
        invalidation_price=inv,
        indicators_snapshot=_snapshot(ind, ["book_imbalance_5", "atr_14"]),
        notes=[f"imbalance={book_imb5:.3f}"],
    )


def signal_volatility_event(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT, interval, asset_role, "no TFState")

    ind = _get_ind(tf)
    vol_ratio = ind.get("volume_ratio", 1.0)
    vwap_dev  = ind.get("vwap_deviation_pct", 0.0)
    atr       = ind.get("atr_14", 0.0)
    close     = tf.bars[-1].close if tf.bars else 0.0

    if vol_ratio < 2.0:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT, interval, asset_role, "no_vol_spike")

    direction = DIRECTION_LONG if vwap_dev > 0.0 else DIRECTION_SHORT
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=2.0, tp_mult=2.5)

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_VOLATILITY_EVENT, interval),
        symbol=sym_state.symbol, family=FAMILY_VOLATILITY_EVENT,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=0.8,
        confluence_votes=4, confluence_total=5,
        risk_reward_ratio=rr, atr_at_signal=atr,
        invalidation_price=inv,
        indicators_snapshot=_snapshot(ind, ["volume_ratio", "vwap_deviation_pct", "atr_14"]),
        notes=[f"vol_ratio={vol_ratio:.2f}"],
    )


def _calc_bar_cvd(tf: TFState) -> List[float]:
    cvd = 0.0
    cvd_vals = []
    for bar in tf.bars:
        diff = bar.close - bar.open
        if diff > 0:
            delta = bar.volume
        elif diff < 0:
            delta = -bar.volume
        else:
            delta = 0.0
        cvd += delta
        cvd_vals.append(cvd)
    return cvd_vals


def signal_cvd_divergence(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:
    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "no TFState")
        
    closes = tf.closes()
    if len(closes) < 15:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "insufficient_data")
        
    cvd_vals = _calc_bar_cvd(tf)
    import factor_math as fm
    div_score = fm.compute_divergence(closes, cvd_vals, fractal_window=2, max_lookback=20)
    
    atr = tf.indicators.get("atr_14", 0.0)
    close = closes[-1]
    
    if div_score < -0.3:
        direction = DIRECTION_LONG
        sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=2.0, tp_mult=2.5)
        return SignalResult(
            signal_id=_make_signal_id(sym_state.symbol, FAMILY_DIVERGENCE, interval),
            symbol=sym_state.symbol, family=FAMILY_DIVERGENCE,
            interval=interval, asset_role=asset_role,
            fired=True, direction=direction,
            entry_price=close, stop_loss=sl,
            take_profit=tp, take_profit_2=tp2,
            confidence_score=abs(div_score),
            confluence_votes=3, confluence_total=5,
            risk_reward_ratio=rr, atr_at_signal=atr,
            invalidation_price=inv,
            indicators_snapshot=_snapshot(tf.indicators, ["atr_14"]),
            notes=[f"bullish_div={div_score:.3f}"],
        )
    elif div_score > 0.3:
        direction = DIRECTION_SHORT
        sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction, sl_mult=2.0, tp_mult=2.5)
        return SignalResult(
            signal_id=_make_signal_id(sym_state.symbol, FAMILY_DIVERGENCE, interval),
            symbol=sym_state.symbol, family=FAMILY_DIVERGENCE,
            interval=interval, asset_role=asset_role,
            fired=True, direction=direction,
            entry_price=close, stop_loss=sl,
            take_profit=tp, take_profit_2=tp2,
            confidence_score=abs(div_score),
            confluence_votes=3, confluence_total=5,
            risk_reward_ratio=rr, atr_at_signal=atr,
            invalidation_price=inv,
            indicators_snapshot=_snapshot(tf.indicators, ["atr_14"]),
            notes=[f"bearish_div={div_score:.3f}"],
        )
        
    return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE, interval, asset_role, "no_divergence")
