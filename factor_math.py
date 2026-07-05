from __future__ import annotations
"""NumPy-accelerated factor and indicator computations.

All functions operate on plain Python lists or numpy arrays and return
plain Python floats/dicts — no external state, easy to unit-test.

Target: each function < 0.2 ms on 500 bars so the full refresh cycle
stays under 5 ms per tick.
"""

from typing import Any, Dict, List, Optional
import numpy as np


def ema_np(values: List[float] | np.ndarray, period: int) -> Optional[float]:
    """Exponential moving average via numpy/scipy — normalized and vectorized."""
    from scipy.signal import lfilter, lfilter_zi
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return None
    alpha = 2.0 / (period + 1)
    b = [alpha]
    a = [1, -(1 - alpha)]
    zi = lfilter_zi(b, a) * arr[0]
    out, _ = lfilter(b, a, arr, zi=zi)
    return float(out[-1])


def macd_np(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    """Return MACD, MACD_signal, MACD_hist as a dict (all floats). Vectorized via scipy.signal.lfilter."""
    arr = np.asarray(closes, dtype=np.float64)
    if arr.size < slow:
        return {"MACD": 0.0, "MACD_signal": 0.0, "MACD_hist": 0.0}

    from scipy.signal import lfilter, lfilter_zi

    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    alpha_sig  = 2.0 / (signal + 1)

    # Fast EMA
    b_fast = [alpha_fast]
    a_fast = [1, -(1 - alpha_fast)]
    zi_fast = lfilter_zi(b_fast, a_fast) * arr[0]
    ema_fast, _ = lfilter(b_fast, a_fast, arr, zi=zi_fast)

    # Slow EMA
    b_slow = [alpha_slow]
    a_slow = [1, -(1 - alpha_slow)]
    zi_slow = lfilter_zi(b_slow, a_slow) * arr[0]
    ema_slow, _ = lfilter(b_slow, a_slow, arr, zi=zi_slow)

    macd_line = ema_fast - ema_slow

    # Signal Line EMA
    b_sig = [alpha_sig]
    a_sig = [1, -(1 - alpha_sig)]
    zi_sig = lfilter_zi(b_sig, a_sig) * macd_line[0]
    sig_line, _ = lfilter(b_sig, a_sig, macd_line, zi=zi_sig)

    macd_val = float(macd_line[-1])
    sig_val  = float(sig_line[-1])
    return {"MACD": macd_val, "MACD_signal": sig_val, "MACD_hist": macd_val - sig_val}


# ── Bollinger Bands ───────────────────────────────────────────────
def bollinger_bands_np(closes: List[float], period: int = 20, num_std: float = 2.0) -> Dict[str, float]:
    """Returns BBANDS_mid, BBANDS_upper, BBANDS_lower, BollingerWidth."""
    arr = np.asarray(closes[-period:], dtype=np.float64)
    if arr.size < 2:
        return {"BBANDS_mid": 0.0, "BBANDS_upper": 0.0, "BBANDS_lower": 0.0, "BollingerWidth": 0.0}
    sma  = float(arr.mean())
    std  = float(arr.std(ddof=0))
    upper = sma + num_std * std
    lower = sma - num_std * std
    width = (upper - lower) / sma if sma else 0.0
    return {"BBANDS_mid": sma, "BBANDS_upper": upper, "BBANDS_lower": lower, "BollingerWidth": width}


# ── Z-Score ───────────────────────────────────────────────────────
def zscore_np(closes: List[float], period: int = 20) -> float:
    """Rolling z-score of latest close vs last `period` closes."""
    arr = np.asarray(closes[-period:], dtype=np.float64)
    if arr.size < 2:
        return 0.0
    mu, sigma = float(arr.mean()), float(arr.std(ddof=0))
    return float((arr[-1] - mu) / sigma) if sigma else 0.0


# ── Relative Volume ───────────────────────────────────────────────
def rel_volume_np(volumes: List[float], period: int = 20) -> float:
    arr = np.asarray(volumes[-period:], dtype=np.float64)
    if arr.size < 2:
        return 0.0
    mean_vol = float(arr[:-1].mean())
    return float(arr[-1] / mean_vol) if mean_vol else 0.0


# ── Trade Flow Imbalance ──────────────────────────────────────────
def flow_imbalance_np(sizes: List[float], sides: List[str], window: int = 20) -> float:
    sz  = np.asarray(sizes[-window:], dtype=np.float64)
    sd  = sides[-window:]
    signs = np.where(np.array(sd) == "B", 1.0, np.where(np.array(sd) == "A", -1.0, 0.0))
    total = sz.sum()
    return float((sz * signs).sum() / total) if total else 0.0


# ── RSI ───────────────────────────────────────────────────────────
def rsi_np(closes: List[float], period: int = 14) -> float:
    """Relative Strength Index via numpy/scipy lfilter matching Wilder's smoothing."""
    arr = np.asarray(closes, dtype=np.float64)
    if arr.size <= period:
        return 50.0
    diff = np.diff(arr)
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)
    
    alpha = 1.0 / period
    b = [alpha]
    a = [1, -(1 - alpha)]
    from scipy.signal import lfilter, lfilter_zi
    
    zi_g = lfilter_zi(b, a) * gains[0]
    avg_g, _ = lfilter(b, a, gains, zi=zi_g)
    
    zi_l = lfilter_zi(b, a) * losses[0]
    avg_l, _ = lfilter(b, a, losses, zi=zi_l)
    
    rs = avg_g[-1] / avg_l[-1] if avg_l[-1] else 0.0
    if avg_l[-1] == 0.0:
        return 50.0 if avg_g[-1] == 0.0 else 100.0
    return float(100.0 - 100.0 / (1.0 + rs))


# ── ATR ───────────────────────────────────────────────────────────
def atr_np(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Average True Range via EMA of True Range."""
    h = np.asarray(highs, dtype=np.float64)
    l = np.asarray(lows, dtype=np.float64)
    c = np.asarray(closes, dtype=np.float64)
    if h.size < period + 1:
        return 0.0
    
    tr = np.zeros_like(h)
    tr[0] = h[0] - l[0]
    for i in range(1, h.size):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
    
    res = ema_np(tr, period)
    return res if res is not None else 0.0


# ── Divergence ────────────────────────────────────────────────────
def find_fractal_peaks(values: List[float] | np.ndarray, window: int = 2) -> List[int]:
    """Returns list of indices where fractal peaks occur."""
    peaks = []
    n = len(values)
    for i in range(window, n - window):
        is_peak = True
        for j in range(1, window + 1):
            if values[i] <= values[i - j] or values[i] <= values[i + j]:
                is_peak = False
                break
        if is_peak:
            peaks.append(i)
    return peaks


def find_fractal_troughs(values: List[float] | np.ndarray, window: int = 2) -> List[int]:
    """Returns list of indices where fractal troughs occur."""
    troughs = []
    n = len(values)
    for i in range(window, n - window):
        is_trough = True
        for j in range(1, window + 1):
            if values[i] >= values[i - j] or values[i] >= values[i + j]:
                is_trough = False
                break
        if is_trough:
            troughs.append(i)
    return troughs


def macd_history_np(closes: List[float], fast: int = 12, slow: int = 26) -> np.ndarray:
    """Returns vector of MACD line values for the entire closes series."""
    arr = np.asarray(closes, dtype=np.float64)
    if arr.size < slow:
        return np.zeros(arr.size)

    from scipy.signal import lfilter, lfilter_zi

    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)

    b_fast = [alpha_fast]
    a_fast = [1, -(1 - alpha_fast)]
    zi_fast = lfilter_zi(b_fast, a_fast) * arr[0]
    ema_fast, _ = lfilter(b_fast, a_fast, arr, zi=zi_fast)

    b_slow = [alpha_slow]
    a_slow = [1, -(1 - alpha_slow)]
    zi_slow = lfilter_zi(b_slow, a_slow) * arr[0]
    ema_slow, _ = lfilter(b_slow, a_slow, arr, zi=zi_slow)

    return ema_fast - ema_slow


def rsi_history_np(closes: List[float], period: int = 14) -> np.ndarray:
    """Returns vector of RSI values for the entire closes series."""
    arr = np.asarray(closes, dtype=np.float64)
    out = np.full(arr.size, 50.0)
    if arr.size <= period:
        return out

    diff = np.diff(arr)
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)

    alpha = 1.0 / period
    b = [alpha]
    a = [1, -(1 - alpha)]
    from scipy.signal import lfilter, lfilter_zi

    zi_g = lfilter_zi(b, a) * gains[0]
    avg_g, _ = lfilter(b, a, gains, zi=zi_g)

    zi_l = lfilter_zi(b, a) * losses[0]
    avg_l, _ = lfilter(b, a, losses, zi=zi_l)

    rs = np.where(avg_l != 0.0, avg_g / avg_l, 0.0)
    rsi_vals = np.where(avg_l == 0.0, np.where(avg_g == 0.0, 50.0, 100.0), 100.0 - 100.0 / (1.0 + rs))

    out[1:] = rsi_vals
    return out


def compute_divergence(
    closes: List[float],
    indicator_values: List[float],
    fractal_window: int = 2,
    max_lookback: int = 30,
    scale_factor: float = 100.0
) -> float:
    """
    Returns divergence score:
      0.0  = no divergence
      > 0  = bearish divergence (indicator weaker than price)
      < 0  = bullish divergence (indicator stronger than price)
    Magnitude: 0.0 to 1.0
    """
    if len(closes) < 2 * fractal_window + 1 or len(closes) != len(indicator_values):
        return 0.0

    price_peaks = find_fractal_peaks(closes, fractal_window)
    price_troughs = find_fractal_troughs(closes, fractal_window)

    ind_peaks = find_fractal_peaks(indicator_values, fractal_window)
    ind_troughs = find_fractal_troughs(indicator_values, fractal_window)

    n = len(closes)
    bullish_score = 0.0
    bearish_score = 0.0

    # Bullish Divergence check
    if len(price_troughs) >= 2 and len(ind_troughs) >= 2:
        p_idx_curr = price_troughs[-1]
        p_idx_prev = price_troughs[-2]
        ind_idx_curr = ind_troughs[-1]
        ind_idx_prev = ind_troughs[-2]
        
        # Check staleness
        if (n - 1 - p_idx_curr <= max_lookback) and (n - 1 - ind_idx_curr <= max_lookback):
            trough_prev = closes[p_idx_prev]
            trough_curr = closes[p_idx_curr]
            ind_trough_prev = indicator_values[ind_idx_prev]
            ind_trough_curr = indicator_values[ind_idx_curr]
            
            # price LL (trough_curr < trough_prev) and indicator HL (ind_trough_curr > ind_trough_prev)
            if trough_curr < trough_prev and ind_trough_curr > ind_trough_prev:
                if trough_prev != 0 and ind_trough_prev != 0:
                    price_diff_pct = (trough_prev - trough_curr) / trough_prev
                    ind_diff_pct = (ind_trough_curr - ind_trough_prev) / abs(ind_trough_prev)
                    bullish_score = -1.0 * min(price_diff_pct * ind_diff_pct * scale_factor, 1.0)

    # Bearish Divergence check
    if len(price_peaks) >= 2 and len(ind_peaks) >= 2:
        p_idx_curr = price_peaks[-1]
        p_idx_prev = price_peaks[-2]
        ind_idx_curr = ind_peaks[-1]
        ind_idx_prev = ind_peaks[-2]
        
        # Check staleness
        if (n - 1 - p_idx_curr <= max_lookback) and (n - 1 - ind_idx_curr <= max_lookback):
            peak_prev = closes[p_idx_prev]
            peak_curr = closes[p_idx_curr]
            ind_peak_prev = indicator_values[ind_idx_prev]
            ind_peak_curr = indicator_values[ind_idx_curr]
            
            # price HH (peak_curr > peak_prev) and indicator LH (ind_peak_curr < ind_peak_prev)
            if peak_curr > peak_prev and ind_peak_curr < ind_peak_prev:
                if peak_prev != 0 and ind_peak_prev != 0:
                    price_diff_pct = (peak_curr - peak_prev) / peak_prev
                    ind_diff_pct = (ind_peak_prev - ind_peak_curr) / abs(ind_peak_prev)
                    bearish_score = +1.0 * min(price_diff_pct * ind_diff_pct * scale_factor, 1.0)

    if bullish_score != 0.0 and bearish_score != 0.0:
        if price_troughs[-1] > price_peaks[-1]:
            return bullish_score
        else:
            return bearish_score
    elif bullish_score != 0.0:
        return bullish_score
    else:
        return bearish_score


# ── Batch factors (drop-in replacement for ResearchEngine methods) ─
def compute_factors_np(closes: List[float], volumes: List[float]) -> Dict[str, float]:
    """Return full factor dict from close/volume arrays."""
    factors: Dict[str, float] = {}
    if len(closes) < 2:
        return factors
    factors["ret_1"] = (closes[-1] / closes[-2] - 1) if closes[-2] else 0.0
    if len(closes) >= 5 and closes[-5]:
        factors["ret_5"] = closes[-1] / closes[-5] - 1
    if len(closes) >= 21:
        arr = np.asarray(closes, dtype=np.float64)
        w20 = arr[-20:]
        mu, sigma = float(w20.mean()), float(w20.std(ddof=0))
        factors["zscore_close_20"] = (closes[-1] - mu) / sigma if sigma else 0.0
        factors["volatility_20"]   = sigma / mu if mu else 0.0

        fast = ema_np(closes[-80:], 8)
        slow = ema_np(closes[-80:], 21)
        if fast is not None and slow is not None and closes[-1]:
            factors["ema_spread_8_21"] = (fast - slow) / closes[-1]

        factors["rel_volume_20"] = rel_volume_np(volumes, 20)
    return factors


def compute_indicators_np(closes: List[float], factors: Dict[str, float]) -> Dict[str, float]:
    """Return full indicator dict."""
    indicators: Dict[str, float] = {}
    if len(closes) < 20:
        return indicators
    indicators.update(bollinger_bands_np(closes, 20))
    if len(closes) >= 35:
        indicators.update(macd_np(closes))
    indicators["ZScore_Close"]   = factors.get("zscore_close_20", 0.0)
    indicators["RelativeVolume"] = factors.get("rel_volume_20", 0.0)
    indicators["TradeFlowImbalance"] = factors.get("trade_flow_imbalance_20", 0.0)
    indicators["MicroVolatility"] = factors.get("micro_volatility_20", 0.0)
    indicators["SpreadBps"]       = factors.get("spread_bps", 0.0)
    indicators["LiveReturnFromClose"] = factors.get("live_ret_from_last_close", 0.0)
    return indicators
