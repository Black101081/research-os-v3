from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from asset_tf_fitness import is_fitness_ok
from multi_tf_state import MultiTFSymbolState, TFState
from signal_models import (
    DIRECTION_BOTH, DIRECTION_LONG, DIRECTION_SHORT,
    FAMILY_BREAKOUT, FAMILY_CONTINUATION, FAMILY_DIVERGENCE,
    FAMILY_FUNDING_REVERSION, FAMILY_MEAN_REVERSION,
    FAMILY_OI_REVERSAL, FAMILY_ORDER_FLOW, FAMILY_VOLATILITY_EVENT,
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
    tp_2 = entry ± 4.0 * atr (high conviction runner target).
    """
    if atr <= 0 or entry <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    if direction == DIRECTION_LONG:
        sl   = entry - sl_mult * atr
        tp   = entry + tp_mult * atr
        tp2  = entry + 4.0 * atr
        inv  = entry - 2.0 * atr   # void if price falls 2 ATR from entry
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
# SIGNAL 1 — MACD Continuation
# Family: continuation | Best TFs: 5m, 15m, 1h | Assets: all
# Logic: MACD bullish/bearish cross + ADX trend confirmation +
#        EMA spread alignment + OBV slope confirm
# ─────────────────────────────────────────────────────────────────────

def signal_macd_continuation(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_CONTINUATION,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_CONTINUATION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_CONTINUATION,
                          interval, asset_role, "fitness_blocked")

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
    vol_q     = ind.get("volume_quality_score", 0.0)

    # Anti-chop filter: ADX must confirm trend
    if adx < 20.0:
        return _no_signal(sym_state.symbol, FAMILY_CONTINUATION,
                          interval, asset_role, f"adx_too_low={adx:.1f}")

    # ── LONG confluence votes ──────────────────────────────
    long_votes = [
        macd > macd_sig,               # MACD above signal
        macd_hist > 0,                 # histogram positive
        ema_sp > 0.03,                 # EMA fast > slow
        rsi > 50 and rsi < 70,         # momentum but not overbought
        obv_sl > 0,                    # OBV accumulating
    ]
    # ── SHORT confluence votes ─────────────────────────────
    short_votes = [
        macd < macd_sig,
        macd_hist < 0,
        ema_sp < -0.03,
        rsi < 50 and rsi > 30,
        obv_sl < 0,
    ]

    long_count  = sum(long_votes)
    short_count = sum(short_votes)
    total_votes = len(long_votes)

    # Require at least 3/5 votes for signal
    direction = None
    votes = 0
    if long_count >= 3 and long_count > short_count:
        direction = DIRECTION_LONG
        votes = long_count
    elif short_count >= 3 and short_count > long_count:
        direction = DIRECTION_SHORT
        votes = short_count

    if direction is None or atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_CONTINUATION,
                          interval, asset_role,
                          f"no_confluence l={long_count} s={short_count}")

    # HTF bias gate: skip if strongly counter-trend
    htf = "1h" if interval in ("5m", "15m") else "15m"
    htf_bias = sym_state.htf_bias(htf)
    mtf_score = sym_state.mtf_alignment()
    if direction == DIRECTION_LONG and htf_bias == "bearish":
        return _no_signal(sym_state.symbol, FAMILY_CONTINUATION,
                          interval, asset_role, "counter_htf_bias=bearish")
    if direction == DIRECTION_SHORT and htf_bias == "bullish":
        return _no_signal(sym_state.symbol, FAMILY_CONTINUATION,
                          interval, asset_role, "counter_htf_bias=bullish")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=1.5, tp_mult=2.5)
    # Boost confidence if volume confirms
    base_conf = votes / total_votes
    conf = min(1.0, base_conf + (0.1 if vol_q > 0.5 else 0.0))

    notes = [
        f"adx={adx:.1f}", f"macd={macd:.4f}>sig={macd_sig:.4f}",
        f"ema_spread={ema_sp:.3f}", f"rsi={rsi:.1f}",
        f"obv_slope={obv_sl:.2f}", f"votes={votes}/{total_votes}",
        f"htf_bias={htf_bias}", f"vol_q={vol_q:.2f}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_CONTINUATION, interval),
        symbol=sym_state.symbol, family=FAMILY_CONTINUATION,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total_votes,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=ind.get("funding_signal", 0.0),
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason=f"price_crosses_{inv:.2f} (2 ATR from entry)",
        indicators_snapshot=_snapshot(ind, [
            "MACD", "MACD_signal", "MACD_histogram", "adx_14",
            "rsi_14", "ema_spread_8_21", "obv_slope_10", "atr_14",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 2 — RSI Divergence
# Family: divergence | Best TFs: 5m, 15m, 1h | Assets: anchor, major
# Logic: RSI diverges from price (higher high price + lower high RSI = bearish div)
#        Confirmed by StochRSI overbought/oversold + volume declining
# ─────────────────────────────────────────────────────────────────────

def signal_rsi_divergence(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_DIVERGENCE, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "fitness_blocked")

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
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "insufficient_context")

    # Detect swing structure: compare last 2 price swings vs RSI
    closes = tf.closes()
    rsi_vals = []   # build mini RSI series for last 20 bars
    from factor_math import calc_rsi as _calc_rsi
    for i in range(max(15, n - 20), n + 1):
        rsi_vals.append(_calc_rsi(closes[:i], 14))

    if len(rsi_vals) < 5:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "rsi_series_short")

    # Find recent highs/lows in price and RSI over last 15 bars
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

    # Bearish divergence: price makes higher high, RSI makes lower high
    bearish_div = (price_high2 > price_high1 * 1.001 and
                   rsi_high2   < rsi_high1   - 2.0 and
                   rsi >= 55)   # RSI still elevated

    # Bullish divergence: price makes lower low, RSI makes higher low
    bullish_div = (price_low2  < price_low1  * 0.999 and
                   rsi_low2    > rsi_low1    + 2.0 and
                   rsi <= 45)   # RSI still depressed

    if not bearish_div and not bullish_div:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "no_divergence_detected")

    direction = DIRECTION_SHORT if bearish_div else DIRECTION_LONG

    # Confluence votes
    if direction == DIRECTION_SHORT:
        votes_list = [
            bearish_div,
            stoch_k > 75,              # StochRSI overbought
            stoch_k < stoch_d,         # StochRSI turning down
            vol_ratio < 0.9,           # volume declining on rally
            bb_pct > 0.85,             # near upper BB
            cmf < 0.0,                 # money outflow
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
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role,
                          f"divergence_detected_but_low_confluence={votes}/{total}")

    htf_bias    = sym_state.htf_bias("1h" if interval in ("5m","15m") else "15m")
    mtf_score   = sym_state.mtf_alignment()
    # Divergence is a reversal signal — allow counter-trend only if strong div
    if direction == DIRECTION_LONG and htf_bias == "bearish" and votes < 5:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "weak_reversal_against_htf_bear")
    if direction == DIRECTION_SHORT and htf_bias == "bullish" and votes < 5:
        return _no_signal(sym_state.symbol, FAMILY_DIVERGENCE,
                          interval, asset_role, "weak_reversal_against_htf_bull")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=1.2, tp_mult=2.0)
    conf = votes / total

    notes = [
        f"{'bearish' if bearish_div else 'bullish'}_divergence",
        f"rsi={rsi:.1f}", f"stoch_k={stoch_k:.1f}",
        f"vol_ratio={vol_ratio:.2f}", f"bb_pct={bb_pct:.2f}",
        f"votes={votes}/{total}", f"htf_bias={htf_bias}",
    ]

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
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=ind.get("funding_signal", 0.0),
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason=f"divergence_void_above_{inv:.2f}",
        indicators_snapshot=_snapshot(ind, [
            "rsi_14", "stoch_rsi_k", "stoch_rsi_d",
            "bb_pct_20", "cmf_20", "volume_ratio", "atr_14",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 3 — BB Squeeze Breakout
# Family: breakout | Best TFs: 5m, 15m | Assets: all
# Logic: BB width at low percentile (squeeze) → price breaks outside band
#        + volume spike confirms + ADX starting to rise
# ─────────────────────────────────────────────────────────────────────

def signal_bb_squeeze_breakout(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_BREAKOUT, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT,
                          interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    bb_width   = ind.get("bb_width_20", 5.0)
    bb_pct     = ind.get("bb_pct_20", 0.5)
    squeeze_sc = ind.get("squeeze_score", 0.0)
    vol_ratio  = ind.get("volume_ratio", 1.0)
    vol_zscore = ind.get("volume_zscore", 0.0)
    adx        = ind.get("adx_14", 0.0)
    atr        = ind.get("atr_14", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    obv_sl     = ind.get("obv_slope_10", 0.0)
    vwap_dev   = ind.get("vwap_deviation_pct", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0
    vol_q      = ind.get("volume_quality_score", 0.0)
    book_imb   = ind.get("book_imbalance_10", 0.0)

    # Squeeze condition: BB width in bottom 30% of its typical range
    # squeeze_score > 0.5 means width is tight
    if squeeze_sc < 0.4:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT,
                          interval, asset_role,
                          f"no_squeeze squeeze_score={squeeze_sc:.2f}")

    # Breakout direction from BB position
    if bb_pct > 0.95:
        direction = DIRECTION_LONG
    elif bb_pct < 0.05:
        direction = DIRECTION_SHORT
    else:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT,
                          interval, asset_role,
                          f"price_not_at_band bb_pct={bb_pct:.2f}")

    # Volume MUST confirm breakout — this is the primary filter
    if vol_ratio < 1.5 and vol_zscore < 1.0:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT,
                          interval, asset_role,
                          f"no_volume_confirmation vol_ratio={vol_ratio:.2f}")

    # Confluence votes
    if direction == DIRECTION_LONG:
        votes_list = [
            bb_pct > 0.95,             # price above upper band
            vol_ratio > 1.5,           # volume spike
            vol_zscore > 1.0,          # unusual volume
            adx > 15,                  # ADX starting (not yet 20)
            rsi > 50 and rsi < 75,     # momentum, not extreme OB
            obv_sl > 0,                # OBV confirms
            vwap_dev > 0,              # above VWAP
            book_imb > 0.1,            # order book bid heavy
        ]
    else:
        votes_list = [
            bb_pct < 0.05,
            vol_ratio > 1.5,
            vol_zscore > 1.0,
            adx > 15,
            rsi < 50 and rsi > 25,
            obv_sl < 0,
            vwap_dev < 0,
            book_imb < -0.1,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 4:
        return _no_signal(sym_state.symbol, FAMILY_BREAKOUT,
                          interval, asset_role,
                          f"low_confluence={votes}/{total}")

    htf_bias  = sym_state.htf_bias("1h" if interval in ("5m","15m") else "15m")
    mtf_score = sym_state.mtf_alignment()

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=1.0, tp_mult=2.0)
    # Breakout SL is tighter: just outside the band (1 ATR)
    conf = min(1.0, votes / total + (0.05 if htf_bias != "neutral" and
               ((direction == DIRECTION_LONG and htf_bias == "bullish") or
                (direction == DIRECTION_SHORT and htf_bias == "bearish")) else 0.0))

    notes = [
        f"squeeze_score={squeeze_sc:.2f}", f"bb_pct={bb_pct:.2f}",
        f"vol_ratio={vol_ratio:.2f}", f"vol_z={vol_zscore:.2f}",
        f"adx={adx:.1f}", f"rsi={rsi:.1f}",
        f"votes={votes}/{total}", f"htf_bias={htf_bias}",
        f"book_imb={book_imb:.3f}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_BREAKOUT, interval),
        symbol=sym_state.symbol, family=FAMILY_BREAKOUT,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=ind.get("funding_signal", 0.0),
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason=f"breakout_false_if_close_back_inside_band",
        indicators_snapshot=_snapshot(ind, [
            "bb_width_20", "bb_pct_20", "squeeze_score",
            "volume_ratio", "volume_zscore", "adx_14", "atr_14",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 4 — Mean Reversion (BB + StochRSI + VWAP)
# Family: mean_reversion | Best TFs: 15m, 1h | Assets: anchor, major
# Logic: Price extreme vs VWAP + BB oversold/overbought +
#        StochRSI reversing + CMF confirming + low ADX (range bound)
# ─────────────────────────────────────────────────────────────────────

def signal_mean_reversion(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_MEAN_REVERSION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION,
                          interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    rsi       = ind.get("rsi_14", 50.0)
    stoch_k   = ind.get("stoch_rsi_k", 50.0)
    stoch_d   = ind.get("stoch_rsi_d", 50.0)
    bb_pct    = ind.get("bb_pct_20", 0.5)
    adx       = ind.get("adx_14", 0.0)
    vwap_dev  = ind.get("vwap_deviation_pct", 0.0)
    cmf       = ind.get("cmf_20", 0.0)
    atr       = ind.get("atr_14", 0.0)
    close     = tf.bars[-1].close if tf.bars else 0.0
    vol_q     = ind.get("volume_quality_score", 0.0)
    funding_s = ind.get("funding_signal", 0.0)

    # Mean reversion requires LOW ADX (range-bound) — opposite of trend signals
    if adx > 28.0:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION,
                          interval, asset_role,
                          f"trending_market adx={adx:.1f}>28, skip MR")

    if atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION,
                          interval, asset_role, "no_atr_or_close")

    # Determine extreme
    long_extreme  = bb_pct < 0.10 and rsi < 35 and vwap_dev < -1.0
    short_extreme = bb_pct > 0.90 and rsi > 65 and vwap_dev > 1.0

    if not long_extreme and not short_extreme:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION,
                          interval, asset_role,
                          f"no_extreme bb={bb_pct:.2f} rsi={rsi:.1f}")

    direction = DIRECTION_LONG if long_extreme else DIRECTION_SHORT

    # StochRSI must be reversing (not just at extreme — needs hook)
    stoch_reversing_long  = stoch_k < 20 and stoch_k > stoch_d
    stoch_reversing_short = stoch_k > 80 and stoch_k < stoch_d

    if direction == DIRECTION_LONG:
        votes_list = [
            bb_pct < 0.10,
            rsi < 35,
            vwap_dev < -1.0,
            stoch_reversing_long,
            cmf > -0.05,               # not severe outflow
            funding_s >= 0,            # funding not against longs
        ]
    else:
        votes_list = [
            bb_pct > 0.90,
            rsi > 65,
            vwap_dev > 1.0,
            stoch_reversing_short,
            cmf < 0.05,
            funding_s <= 0,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 4:
        return _no_signal(sym_state.symbol, FAMILY_MEAN_REVERSION,
                          interval, asset_role,
                          f"insufficient_confluence={votes}/{total}")

    # MR: use tighter SL (1.0 ATR) and smaller TP (1.5 ATR — revert to mean)
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=1.0, tp_mult=1.5)
    # TP should be near VWAP, cap it
    vwap = ind.get("vwap", close)
    if direction == DIRECTION_LONG and vwap > close:
        tp = min(tp, vwap)   # target is VWAP, not further
    elif direction == DIRECTION_SHORT and vwap < close:
        tp = max(tp, vwap)

    htf_bias  = sym_state.htf_bias("1h" if interval == "15m" else "4h")
    mtf_score = sym_state.mtf_alignment()
    conf = votes / total

    notes = [
        f"bb_pct={bb_pct:.2f}", f"rsi={rsi:.1f}",
        f"vwap_dev={vwap_dev:.2f}%", f"adx={adx:.1f}",
        f"stoch_k={stoch_k:.1f}", f"cmf={cmf:.3f}",
        f"votes={votes}/{total}", f"tp_at_vwap={tp:.2f}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_MEAN_REVERSION, interval),
        symbol=sym_state.symbol, family=FAMILY_MEAN_REVERSION,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=funding_s,
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason="mean_reversion_void_if_price_extends_extreme",
        indicators_snapshot=_snapshot(ind, [
            "rsi_14", "stoch_rsi_k", "stoch_rsi_d",
            "bb_pct_20", "vwap_deviation_pct", "adx_14",
            "cmf_20", "atr_14", "vwap",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 5 — Order Flow Imbalance
# Family: order_flow | Best TFs: 1m, 5m | Assets: anchor (BTC), major
# Logic: Orderbook bid/ask imbalance extreme + OBV spike + price vs VWAP
#        + CMF direction + volume zscore
# ─────────────────────────────────────────────────────────────────────

def signal_order_flow_imbalance(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_ORDER_FLOW, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW,
                          interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    book_imb5  = ind.get("book_imbalance_5",  0.0)
    book_imb10 = ind.get("book_imbalance_10", 0.0)
    obv_sl     = ind.get("obv_slope_10", 0.0)
    vol_zscore = ind.get("volume_zscore", 0.0)
    cmf        = ind.get("cmf_20", 0.0)
    vwap_dev   = ind.get("vwap_deviation_pct", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    atr        = ind.get("atr_14", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0
    vol_q      = ind.get("volume_quality_score", 0.0)

    # Order flow signals need significant imbalance threshold
    if abs(book_imb5) < 0.25:
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW,
                          interval, asset_role,
                          f"book_imb_too_low={book_imb5:.3f}")

    direction = DIRECTION_LONG if book_imb5 > 0 else DIRECTION_SHORT

    if direction == DIRECTION_LONG:
        votes_list = [
            book_imb5  > 0.25,         # strong bid pressure top 5
            book_imb10 > 0.15,         # confirmed at top 10
            obv_sl     > 0,            # OBV accumulating
            vol_zscore > 0.5,          # above-average volume
            cmf        > 0.0,          # money flow positive
            vwap_dev   > -0.5,         # not too far below VWAP
            rsi        < 65,           # not overbought
        ]
    else:
        votes_list = [
            book_imb5  < -0.25,
            book_imb10 < -0.15,
            obv_sl     < 0,
            vol_zscore > 0.5,
            cmf        < 0.0,
            vwap_dev   < 0.5,
            rsi        > 35,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 4:
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW,
                          interval, asset_role,
                          f"low_order_flow_confluence={votes}/{total}")

    if atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_ORDER_FLOW,
                          interval, asset_role, "no_atr")

    # Order flow: tightest SL (0.8 ATR), moderate TP (1.5 ATR)
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=0.8, tp_mult=1.5)

    htf_bias  = sym_state.htf_bias("5m" if interval == "1m" else "15m")
    mtf_score = sym_state.mtf_alignment()
    conf = votes / total

    notes = [
        f"book_imb5={book_imb5:.3f}", f"book_imb10={book_imb10:.3f}",
        f"obv_slope={obv_sl:.2f}", f"vol_z={vol_zscore:.2f}",
        f"cmf={cmf:.3f}", f"vwap_dev={vwap_dev:.2f}%",
        f"votes={votes}/{total}", f"htf_bias={htf_bias}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_ORDER_FLOW, interval),
        symbol=sym_state.symbol, family=FAMILY_ORDER_FLOW,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=ind.get("funding_signal", 0.0),
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason="order_flow_void_if_book_flips",
        indicators_snapshot=_snapshot(ind, [
            "book_imbalance_5", "book_imbalance_10",
            "obv_slope_10", "volume_zscore", "cmf_20",
            "vwap_deviation_pct", "atr_14",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 6 — Volatility Event (Volume Spike + ATR expansion)
# Family: volatility_event | Best TFs: 1m, 5m | Assets: all
# Logic: Volume spike (>2x baseline) + ATR expanding + price vs VWAP
#        + book imbalance resolving direction of move
# ─────────────────────────────────────────────────────────────────────

def signal_volatility_event(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_VOLATILITY_EVENT, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT,
                          interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    vol_ratio  = ind.get("volume_ratio", 1.0)
    vol_zscore = ind.get("volume_zscore", 0.0)
    atr_pct    = ind.get("atr_14_pct", 0.0)
    bb_width   = ind.get("bb_width_20", 2.0)
    book_imb   = ind.get("book_imbalance_10", 0.0)
    vwap_dev   = ind.get("vwap_deviation_pct", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    atr        = ind.get("atr_14", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0
    vol_q      = ind.get("volume_quality_score", 0.0)

    # Require significant volume spike — this is the primary trigger
    if vol_ratio < 2.0 and vol_zscore < 2.0:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT,
                          interval, asset_role,
                          f"no_vol_spike ratio={vol_ratio:.2f} z={vol_zscore:.2f}")

    # Direction: follow the spike (momentum, not counter-trade)
    if vwap_dev > 0.3 or book_imb > 0.2:
        direction = DIRECTION_LONG
    elif vwap_dev < -0.3 or book_imb < -0.2:
        direction = DIRECTION_SHORT
    else:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT,
                          interval, asset_role,
                          f"direction_ambiguous vwap_dev={vwap_dev:.2f} imb={book_imb:.3f}")

    votes_list = [
        vol_ratio > 2.0,
        vol_zscore > 2.0,
        atr_pct > 0.3,                 # ATR expanding
        bb_width > 2.0,                # bands expanding
        abs(book_imb) > 0.1,           # directional order flow
        abs(vwap_dev) > 0.3,           # meaningful VWAP deviation
    ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 3:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT,
                          interval, asset_role,
                          f"low_vol_event_confluence={votes}/{total}")

    if atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_VOLATILITY_EVENT,
                          interval, asset_role, "no_atr")

    # Wider SL for volatile moves (2.0 ATR), moderate TP (2.5 ATR)
    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=2.0, tp_mult=2.5)

    htf_bias  = sym_state.htf_bias("5m" if interval == "1m" else "15m")
    mtf_score = sym_state.mtf_alignment()
    conf = min(1.0, votes / total + 0.1 * (vol_ratio / 3.0))

    notes = [
        f"vol_ratio={vol_ratio:.2f}", f"vol_z={vol_zscore:.2f}",
        f"atr_pct={atr_pct:.3f}%", f"book_imb={book_imb:.3f}",
        f"vwap_dev={vwap_dev:.2f}%", f"votes={votes}/{total}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_VOLATILITY_EVENT, interval),
        symbol=sym_state.symbol, family=FAMILY_VOLATILITY_EVENT,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=ind.get("funding_signal", 0.0),
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason="vol_event_void_if_volume_collapses_next_bar",
        indicators_snapshot=_snapshot(ind, [
            "volume_ratio", "volume_zscore", "atr_14_pct",
            "bb_width_20", "book_imbalance_10", "vwap_deviation_pct",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 7 — Funding Rate Reversion (CRYPTO-NATIVE)
# Family: funding_reversion | Best TFs: 5m, 15m | Assets: anchor, major
# Logic: Funding rate z-score extreme → over-leveraged position likely to unwind
#        Confirmed by OI declining + price at resistance/support + RSI extreme
# ─────────────────────────────────────────────────────────────────────

def signal_funding_reversion(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_FUNDING_REVERSION,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_FUNDING_REVERSION, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_FUNDING_REVERSION,
                          interval, asset_role, "fitness_blocked")

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
    vol_q      = ind.get("volume_quality_score", 0.0)

    # Must have extreme funding
    if abs(funding_z) < 2.0:
        return _no_signal(sym_state.symbol, FAMILY_FUNDING_REVERSION,
                          interval, asset_role,
                          f"funding_z_not_extreme={funding_z:.2f}")

    # Positive extreme funding = longs over-leveraged → expect short squeeze unwind
    # → trade SHORT (fade the longs)
    # Negative extreme funding = shorts over-leveraged → trade LONG
    direction = DIRECTION_SHORT if funding_z > 2.0 else DIRECTION_LONG

    if direction == DIRECTION_SHORT:
        votes_list = [
            funding_z > 2.0,           # extreme positive funding
            funding_r > 0.0003,        # significant absolute funding
            oi_mom < 0,                # OI starting to decline
            rsi > 60,                  # momentum elevated
            bb_pct > 0.7,              # price at upper region
            oi_trend <= 0,             # OI trend flat/down
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

    if votes < 3:
        return _no_signal(sym_state.symbol, FAMILY_FUNDING_REVERSION,
                          interval, asset_role,
                          f"low_funding_confluence={votes}/{total}")

    if atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_FUNDING_REVERSION,
                          interval, asset_role, "no_atr")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=1.5, tp_mult=2.0)

    htf_bias  = sym_state.htf_bias("1h" if interval in ("5m","15m") else "15m")
    mtf_score = sym_state.mtf_alignment()
    conf = votes / total

    notes = [
        f"funding_z={funding_z:.2f}", f"funding_rate={funding_r:.6f}",
        f"oi_mom={oi_mom:.2f}", f"rsi={rsi:.1f}",
        f"bb_pct={bb_pct:.2f}", f"votes={votes}/{total}",
        f"htf_bias={htf_bias}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_FUNDING_REVERSION, interval),
        symbol=sym_state.symbol, family=FAMILY_FUNDING_REVERSION,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=funding_s,
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason="funding_reversion_void_if_funding_normalizes",
        indicators_snapshot=_snapshot(ind, [
            "funding_zscore", "funding_rate", "oi_momentum_5",
            "rsi_14", "bb_pct_20", "atr_14",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# SIGNAL 8 — Open Interest Reversal (CRYPTO-NATIVE)
# Family: oi_reversal | Best TFs: 5m, 15m | Assets: anchor, major
# Logic: Open Interest momentum extreme or divergence vs price trend
#        Confirmed by funding rate bias + book imbalance + RSI
# ─────────────────────────────────────────────────────────────────────

def signal_oi_reversal(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalResult:

    tf = sym_state.get_tf(interval)
    if tf is None:
        return _no_signal(sym_state.symbol, FAMILY_OI_REVERSAL,
                          interval, asset_role, "no TFState")

    n = len(tf.bars)
    if not is_fitness_ok(FAMILY_OI_REVERSAL, asset_role, interval, n):
        return _no_signal(sym_state.symbol, FAMILY_OI_REVERSAL,
                          interval, asset_role, "fitness_blocked")

    ind = _get_ind(tf)
    oi_mom     = ind.get("oi_momentum_5", 0.0)
    oi_trend   = ind.get("oi_trend", 0.0)
    rsi        = ind.get("rsi_14", 50.0)
    bb_pct     = ind.get("bb_pct_20", 0.5)
    atr        = ind.get("atr_14", 0.0)
    close      = tf.bars[-1].close if tf.bars else 0.0
    vol_q      = ind.get("volume_quality_score", 0.0)
    funding_s  = ind.get("funding_signal", 0.0)
    book_imb   = ind.get("book_imbalance_10", 0.0)

    # Require significant OI movement to trigger reversal
    if abs(oi_mom) < 1.0 and oi_trend == 0.0:
        return _no_signal(sym_state.symbol, FAMILY_OI_REVERSAL,
                          interval, asset_role, f"oi_not_reversing={oi_mom:.2f}")

    # OI Reversal scenarios: price at extreme + OI declining (meaning position unwinding, fueling reversal)
    long_trigger  = bb_pct < 0.25 and oi_mom < -1.0
    short_trigger = bb_pct > 0.75 and oi_mom < -1.0

    if not long_trigger and not short_trigger:
        return _no_signal(sym_state.symbol, FAMILY_OI_REVERSAL,
                          interval, asset_role, f"no_extreme_with_oi_decline bb_pct={bb_pct:.2f} oi_mom={oi_mom:.2f}")

    direction = DIRECTION_LONG if long_trigger else DIRECTION_SHORT

    if direction == DIRECTION_LONG:
        votes_list = [
            bb_pct < 0.25,
            oi_mom < -1.0,
            rsi < 45,
            book_imb > 0.05,           # bids showing up
            funding_s >= 0.0,          # funding not overly bearish
            vol_q > 0.3,
        ]
    else:
        votes_list = [
            bb_pct > 0.75,
            oi_mom < -1.0,
            rsi > 55,
            book_imb < -0.05,          # asks showing up
            funding_s <= 0.0,
            vol_q > 0.3,
        ]

    votes = sum(votes_list)
    total = len(votes_list)

    if votes < 3:
        return _no_signal(sym_state.symbol, FAMILY_OI_REVERSAL,
                          interval, asset_role, f"low_oi_confluence={votes}/{total}")

    if atr == 0 or close == 0:
        return _no_signal(sym_state.symbol, FAMILY_OI_REVERSAL,
                          interval, asset_role, "no_atr")

    sl, tp, tp2, rr, inv = _calc_levels(close, atr, direction,
                                        sl_mult=1.5, tp_mult=2.5)

    htf_bias  = sym_state.htf_bias("1h" if interval in ("5m","15m") else "15m")
    mtf_score = sym_state.mtf_alignment()
    conf = votes / total

    notes = [
        f"oi_mom={oi_mom:.2f}", f"oi_trend={oi_trend:.1f}",
        f"rsi={rsi:.1f}", f"bb_pct={bb_pct:.2f}",
        f"book_imb={book_imb:.3f}", f"votes={votes}/{total}",
    ]

    return SignalResult(
        signal_id=_make_signal_id(sym_state.symbol, FAMILY_OI_REVERSAL, interval),
        symbol=sym_state.symbol, family=FAMILY_OI_REVERSAL,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=close, stop_loss=sl,
        take_profit=tp, take_profit_2=tp2,
        confidence_score=conf,
        confluence_votes=votes, confluence_total=total,
        risk_reward_ratio=rr, atr_at_signal=atr,
        htf_bias=htf_bias, mtf_alignment=mtf_score,
        funding_signal=funding_s,
        volume_quality_score=vol_q,
        invalidation_price=inv,
        invalidation_reason="oi_reversal_void_if_oi_spikes_again",
        indicators_snapshot=_snapshot(ind, [
            "oi_momentum_5", "oi_trend", "rsi_14",
            "bb_pct_20", "book_imbalance_10", "atr_14",
        ]),
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────

def evaluate_all_signals(
    sym_state: MultiTFSymbolState,
    interval: str,
    asset_role: str,
) -> SignalBatch:
    """Evaluate all 8 signals for a given symbol, timeframe, and role."""
    results = [
        signal_macd_continuation(sym_state, interval, asset_role),
        signal_rsi_divergence(sym_state, interval, asset_role),
        signal_bb_squeeze_breakout(sym_state, interval, asset_role),
        signal_mean_reversion(sym_state, interval, asset_role),
        signal_order_flow_imbalance(sym_state, interval, asset_role),
        signal_volatility_event(sym_state, interval, asset_role),
        signal_funding_reversion(sym_state, interval, asset_role),
        signal_oi_reversal(sym_state, interval, asset_role),
    ]
    return SignalBatch(
        symbol=sym_state.symbol,
        interval=interval,
        results=results,
    )
