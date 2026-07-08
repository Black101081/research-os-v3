from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import factor_math as fm
from multi_tf_state import MultiTFSymbolState, TFState

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────
# Minimum bars required per indicator group.
# Anything below → skip (do not write stale NaN-equivalent 0.0 for trend indicators)
# ─────────────────────────────────────────────────────────────────────
MIN_BARS: Dict[str, int] = {
    "volume":          5,
    "rsi":            15,
    "macd":           35,
    "adx":            29,   # 2 * 14 + 1
    "bb":             20,
    "stoch_rsi":      36,
    "cmf":            20,
    "obv":             5,
    "vwap":            5,
    "poc":             5,
    "ema_spread":      21,
    "parkinson_vol":   20,
    "keltner":         20,
    "cmo":             10,
    "supertrend":      11,
    "stochastic":      17,
    "cci":             20,
    "mfi":             15,
    "emv":             15,
    "vol_profile_va":  10,
    "candle_patterns":  2,
}


def compute_tf_indicators(
    tf_state: TFState,
    sym_state: Optional[MultiTFSymbolState] = None,
    funding_history: Optional[List[float]] = None,
    oi_history: Optional[List[float]] = None,
    best_bid: float = 0.0,
    best_ask: float = 0.0,
) -> None:
    """
    Compute all relevant indicators for a single (symbol, interval) TFState.
    Results are written directly into tf_state.indicators (dict).
    This function is idempotent — safe to call after every new bar.
    """
    ind = tf_state.indicators
    closes  = tf_state.closes()
    highs   = tf_state.highs()
    lows    = tf_state.lows()
    opens   = tf_state.opens()
    volumes = tf_state.volumes()
    n = len(closes)

    if n < 2:
        return   # Nothing useful to compute

    # ── CANDLESTICK PATTERNS ────────────────────────────────────────
    if n >= MIN_BARS["candle_patterns"]:
        patterns = fm.calc_candle_patterns(opens, highs, lows, closes)
        for pat, val in patterns.items():
            ind[f"pattern_{pat}"] = val

    # ── VOLUME INDICATORS ──────────────────────────────────────────
    if n >= MIN_BARS["vwap"]:
        vwap = fm.calc_vwap(closes, volumes)
        ind["vwap"] = vwap
        ind["vwap_deviation_pct"] = fm.calc_vwap_deviation(closes[-1], vwap)

    if n >= MIN_BARS["volume"]:
        ind["volume_ratio"]  = fm.calc_volume_ratio(volumes, window=20)
        ind["volume_zscore"] = fm.calc_volume_zscore(volumes, window=20)
        ind["obv"]           = fm.calc_obv(closes, volumes)
        ind["obv_slope_10"]  = fm.calc_obv_slope(closes, volumes, window=10)

    if n >= MIN_BARS["poc"]:
        ind["volume_poc"] = fm.calc_volume_poc(closes, volumes, bins=20)
        ind["price_vs_poc_pct"] = float(
            (closes[-1] - ind["volume_poc"]) / ind["volume_poc"] * 100
        ) if ind.get("volume_poc", 0) else 0.0

    if n >= MIN_BARS["cmf"]:
        ind["cmf_20"] = fm.calc_cmf(highs, lows, closes, volumes, period=20)

    if n >= MIN_BARS["mfi"]:
        ind["mfi_14"] = fm.calc_mfi(highs, lows, closes, volumes, period=14)

    if n >= MIN_BARS["emv"]:
        ind["emv_14"] = fm.calc_ease_of_movement(highs, lows, volumes, period=14)

    if n >= MIN_BARS["vol_profile_va"]:
        va = fm.calc_volume_profile_va(closes, volumes)
        ind["vol_profile_poc"] = va["poc"]
        ind["vol_profile_vah"] = va["vah"]
        ind["vol_profile_val"] = va["val"]

    # ── VOLATILITY ─────────────────────────────────────────────────
    if n >= 15:
        ind["atr_14"]     = fm.calc_atr(highs, lows, closes, period=14)
        ind["atr_14_pct"] = fm.calc_atr_pct(highs, lows, closes, period=14)

    if n >= MIN_BARS["bb"]:
        ind["bb_width_20"]  = fm.calc_bb_width(closes, period=20)
        ind["bb_pct_20"]    = fm.calc_bb_pct(closes, period=20)

    if n >= MIN_BARS["parkinson_vol"]:
        ind["parkinson_volatility_20"] = fm.calc_parkinson_volatility(highs, lows, period=20)

    if n >= MIN_BARS["keltner"]:
        kc = fm.calc_keltner_channels(highs, lows, closes)
        ind["kc_mid"]   = kc["kc_mid"]
        ind["kc_upper"] = kc["kc_upper"]
        ind["kc_lower"] = kc["kc_lower"]

    # ── RSI ────────────────────────────────────────────────────────
    if n >= MIN_BARS["rsi"]:
        ind["rsi_14"] = fm.calc_rsi(closes, period=14)
        ind["rsi_7"]  = fm.calc_rsi(closes, period=7)

    # ── MACD ───────────────────────────────────────────────────────
    if n >= MIN_BARS["macd"]:
        macd_line, signal_line, histogram = fm.calc_macd(closes, 12, 26, 9)
        ind["MACD"]           = macd_line
        ind["MACD_signal"]    = signal_line
        ind["MACD_histogram"] = histogram
        ind["MACD_cross"]     = float(
            1.0 if (macd_line > signal_line and histogram > 0) else
           -1.0 if (macd_line < signal_line and histogram < 0) else 0.0
        )

    # ── ADX & TREND/MOMENTUM ───────────────────────────────────────
    if n >= MIN_BARS["adx"]:
        ind["adx_14"] = fm.calc_adx(highs, lows, closes, period=14)

    if n >= MIN_BARS["cmo"]:
        ind["cmo_9"] = fm.calc_cmo(closes, period=9)

    if n >= MIN_BARS["supertrend"]:
        st_val, st_dir = fm.calc_supertrend(highs, lows, closes)
        ind["supertrend"] = st_val
        ind["supertrend_direction"] = st_dir

    if n >= MIN_BARS["stochastic"]:
        stoch_k, stoch_d = fm.calc_stochastic_oscillator(highs, lows, closes)
        ind["stoch_k"] = stoch_k
        ind["stoch_d"] = stoch_d

    if n >= MIN_BARS["cci"]:
        ind["cci_20"] = fm.calc_cci(highs, lows, closes, period=20)

    # ── EMA SPREAD ─────────────────────────────────────────────────
    if n >= MIN_BARS["ema_spread"]:
        ind["ema_spread_8_21"] = fm.calc_ema_spread(closes, fast=8, slow=21)
        ind["ema_8"]  = fm.calc_ema(closes, 8)
        ind["ema_21"] = fm.calc_ema(closes, 21)
        ind["ema_50"] = fm.calc_ema(closes, 50) if n >= 50 else closes[-1]

    # ── STOCH RSI ──────────────────────────────────────────────────
    if n >= MIN_BARS["stoch_rsi"]:
        stoch_k, stoch_d = fm.calc_stoch_rsi(closes)
        ind["stoch_rsi_k"] = stoch_k
        ind["stoch_rsi_d"] = stoch_d

    # ── CRYPTO-NATIVE: SPREAD BPS (from live best bid/ask) ─────────
    if best_bid > 0 and best_ask > 0:
        ind["spread_bps"] = fm.calc_spread_bps(best_bid, best_ask)

    # ── CRYPTO-NATIVE: ORDERBOOK IMBALANCE ────────────────────────
    if sym_state is not None:
        if sym_state.bid_levels or sym_state.ask_levels:
            ind["book_imbalance_10"] = fm.calc_bid_ask_imbalance(
                sym_state.bid_levels, sym_state.ask_levels, top_n=10
            )
            ind["book_imbalance_5"] = fm.calc_bid_ask_imbalance(
                sym_state.bid_levels, sym_state.ask_levels, top_n=5
            )

        # Price vs previous day close
        if sym_state.prev_day_px > 0 and closes:
            ind["price_vs_prev_day_pct"] = fm.calc_price_vs_prev_day(
                closes[-1], sym_state.prev_day_px
            )

    # ── CRYPTO-NATIVE: FUNDING RATE ────────────────────────────────
    if funding_history and len(funding_history) >= 3:
        ind["funding_zscore"] = fm.calc_funding_zscore(funding_history)
        ind["funding_rate"]   = float(funding_history[-1])
        # Funding signal: extreme positive = over-leveraged longs → bearish bias
        fz = ind["funding_zscore"]
        ind["funding_signal"] = float(
            -1.0 if fz > 2.0 else
             1.0 if fz < -2.0 else
             0.0
        )

    # ── CRYPTO-NATIVE: OPEN INTEREST MOMENTUM ─────────────────────
    if oi_history and len(oi_history) >= 6:
        ind["oi_momentum_5"] = fm.calc_oi_momentum(oi_history, period=5)
        ind["oi"] = float(oi_history[-1])
        # Interpret: + = new money entering, - = positions closing
        ind["oi_trend"] = float(
             1.0 if ind["oi_momentum_5"] > 2.0 else
            -1.0 if ind["oi_momentum_5"] < -2.0 else
             0.0
        )

    # ── COMPOSITE SCORES ──────────────────────────────────────────
    # Aggregated scores used by signal_generator.py
    # momentum_score: -1.0 (bearish) → +1.0 (bullish)
    momentum_votes = []
    if "rsi_14" in ind:
        rsi = ind["rsi_14"]
        momentum_votes.append(1.0 if rsi > 60 else -1.0 if rsi < 40 else 0.0)
    if "MACD_cross" in ind:
        momentum_votes.append(ind["MACD_cross"])
    if "ema_spread_8_21" in ind:
        spread = ind["ema_spread_8_21"]
        momentum_votes.append(1.0 if spread > 0.05 else -1.0 if spread < -0.05 else 0.0)
    if "obv_slope_10" in ind:
        momentum_votes.append(1.0 if ind["obv_slope_10"] > 0 else -1.0)
    if momentum_votes:
        ind["momentum_score"] = float(sum(momentum_votes) / len(momentum_votes))

    # volume_quality_score: 0.0 (no conviction) → 1.0 (strong volume)
    vq_votes = []
    if "volume_ratio" in ind:
        vq_votes.append(min(ind["volume_ratio"] / 2.0, 1.0))
    if "cmf_20" in ind:
        vq_votes.append(abs(ind["cmf_20"]))
    if "book_imbalance_10" in ind:
        vq_votes.append(abs(ind["book_imbalance_10"]))
    if vq_votes:
        ind["volume_quality_score"] = float(sum(vq_votes) / len(vq_votes))

    # squeeze_score: 1.0 = max squeeze (breakout setup), 0.0 = no squeeze
    if "bb_width_20" in ind:
        # Relative to 50-bar rolling max of bb_width
        ind["squeeze_score"] = float(
            max(0.0, 1.0 - ind["bb_width_20"] / 5.0)   # 5% = wide, scale to 0
        )


# ─────────────────────────────────────────────────────────────────────
# Convenience: run for ALL TF states of a symbol at once
# ─────────────────────────────────────────────────────────────────────

def compute_all_tf_indicators(
    sym_state: MultiTFSymbolState,
    funding_history: Optional[List[float]] = None,
    oi_history: Optional[List[float]] = None,
    best_bid: float = 0.0,
    best_ask: float = 0.0,
) -> None:
    """
    Compute indicators for every TFState of a symbol.
    Call this after any candle bar arrives for the symbol.
    """
    for interval, tf_state in sym_state.tf_states.items():
        compute_tf_indicators(
            tf_state=tf_state,
            sym_state=sym_state,
            funding_history=funding_history,
            oi_history=oi_history,
            best_bid=best_bid,
            best_ask=best_ask,
        )
