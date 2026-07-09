from __future__ import annotations
"""NumPy-accelerated factor and indicator computations.

All functions operate on plain Python lists or numpy arrays and return
plain Python floats/dicts — no external state, easy to unit-test.

Target: each function < 0.2 ms on 500 bars so the full refresh cycle
stays under 5 ms per tick.
"""

from typing import Any, Dict, List, Optional
import numpy as np

try:
    from scipy.signal import lfilter, lfilter_zi
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

    def lfilter_zi(b, a):
        alpha = b[0]
        return np.array([1.0 - alpha], dtype=np.float64)

    def lfilter(b, a, x, zi=None):
        alpha = b[0]
        y = np.zeros_like(x, dtype=np.float64)
        if len(x) == 0:
            return y, zi
        state = zi[0] if zi is not None else 0.0
        for t in range(len(x)):
            y[t] = alpha * x[t] + state
            state = (1 - alpha) * y[t]
        return y, np.array([state])


# Graceful fallback for argrelextrema as requested by reviewer
try:
    from scipy.signal import argrelextrema
    _HAS_SCIPY_EXTREMA = True
except ImportError:
    _HAS_SCIPY_EXTREMA = False
    def argrelextrema(data, comparator, **kwargs):
        # fallback đơn giản: tìm local extrema thủ công
        import numpy as np
        result = []
        order = kwargs.get('order', 1)
        for i in range(order, len(data) - order):
            window = data[i-order:i+order+1]
            if comparator(data[i], window).all():
                result.append(i)
        return (np.array(result),)


def wma_np(values: List[float] | np.ndarray, period: int) -> float:
    """Weighted Moving Average."""
    arr = np.asarray(values, dtype=np.float64)
    if arr.size < period:
        return float(arr[-1]) if arr.size > 0 else 0.0
    weights = np.arange(1, period + 1, dtype=np.float64)
    sub = arr[-period:]
    return float(np.dot(sub, weights) / weights.sum())


def hma_np(values: List[float] | np.ndarray, period: int) -> float:
    """Hull Moving Average - Lag-less moving average."""
    arr = np.asarray(values, dtype=np.float64)
    if arr.size < period:
        return float(arr[-1]) if arr.size > 0 else 0.0
    
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    if sqrt_period < 1:
        sqrt_period = 1
        
    raw_hma_series = []
    for i in range(arr.size - sqrt_period, arr.size):
        sub_arr = arr[:i+1]
        wma_half = wma_np(sub_arr, half_period)
        wma_full = wma_np(sub_arr, period)
        raw_hma_series.append(2.0 * wma_half - wma_full)
        
    return wma_np(raw_hma_series, sqrt_period)


def ema_np(values: List[float] | np.ndarray, period: int) -> Optional[float]:
    """Exponential moving average via numpy/scipy — normalized and vectorized."""
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
    
    zi_g = lfilter_zi(b, a) * gains[0]
    avg_g, _ = lfilter(b, a, gains, zi=zi_g)
    
    zi_l = lfilter_zi(b, a) * losses[0]
    avg_l, _ = lfilter(b, a, losses, zi=zi_l)
    
    rs = avg_g[-1] / avg_l[-1] if avg_l[-1] else 0.0
    if avg_l[-1] == 0.0:
        return 50.0 if avg_g[-1] == 0.0 else 100.0
    return float(100.0 - 100.0 / (1.0 + rs))


def rsi_hma_np(closes: List[float], period: int = 14) -> float:
    """Relative Strength Index smoothed using Hull Moving Average for lag-less response."""
    arr = np.asarray(closes, dtype=np.float64)
    if arr.size <= period:
        return 50.0
    diff = np.diff(arr)
    gains = np.where(diff > 0, diff, 0.0)
    losses = np.where(diff < 0, -diff, 0.0)
    
    avg_g = hma_np(gains, period)
    avg_l = hma_np(losses, period)
    
    if avg_l == 0.0:
        return 100.0 if avg_g > 0.0 else 50.0
    rs = avg_g / avg_l
    return float(100.0 - (100.0 / (1.0 + rs)))


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
    if not _HAS_SCIPY and not _HAS_SCIPY:
        # nếu dùng argrelextrema fallback thì vẫn chạy được
        pass
    if len(closes) < 10 or len(indicator_values) < 10:
        return 0.0

    try:
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
    except Exception:
        return 0.0


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
    indicators["HMA_Close_20"]    = hma_np(closes, 20)
    indicators["RSI_HMA_14"]      = rsi_hma_np(closes, 14)
    return indicators


# ─────────────────────────────────────────────────────────────────────
# A1. VOLUME INDICATORS
# ─────────────────────────────────────────────────────────────────────

def calc_vwap(closes: list, volumes: list) -> float:
    """
    Session VWAP = sum(close * volume) / sum(volume).
    Uses all bars provided — caller slices to session window.
    Returns closes[-1] if total volume is 0 (graceful fallback).
    """
    if len(closes) != len(volumes) or not closes:
        return float(closes[-1]) if closes else 0.0
    c = np.array(closes, dtype=float)
    v = np.array(volumes, dtype=float)
    total_v = v.sum()
    return float((c * v).sum() / total_v) if total_v > 0 else float(c[-1])


def calc_vwap_deviation(close: float, vwap: float) -> float:
    """
    Percent deviation of current close from VWAP.
    > 0 = above VWAP (bullish), < 0 = below VWAP (bearish).
    """
    if vwap == 0:
        return 0.0
    return float((close - vwap) / vwap * 100)


def calc_volume_ratio(volumes: list, window: int = 20) -> float:
    """
    Current bar volume / SMA(volume, window).
    > 1.5 = elevated, > 2.0 = spike, < 0.5 = dry.
    Returns 1.0 if insufficient bars.
    """
    if len(volumes) < window + 1:
        return 1.0
    v = np.array(volumes, dtype=float)
    baseline = v[-(window+1):-1].mean()   # exclude current bar from baseline
    return float(v[-1] / baseline) if baseline > 0 else 1.0


def calc_volume_zscore(volumes: list, window: int = 20) -> float:
    """
    Z-score of current volume vs rolling window.
    Measures how unusual the current bar's volume is.
    Returns 0.0 if insufficient data.
    """
    if len(volumes) < window + 1:
        return 0.0
    v = np.array(volumes, dtype=float)
    window_v = v[-(window+1):-1]
    mu = window_v.mean()
    sigma = window_v.std()
    return float((v[-1] - mu) / sigma) if sigma > 0 else 0.0


def calc_obv(closes: list, volumes: list) -> float:
    """
    On-Balance Volume (last value).
    OBV[i] = OBV[i-1] + volume if close > prev_close, else - volume.
    Returns raw OBV value; use slope for signal (see calc_obv_slope).
    """
    if len(closes) < 2 or len(volumes) < 2:
        return 0.0
    c = np.array(closes, dtype=float)
    v = np.array(volumes, dtype=float)
    signs = np.where(c[1:] > c[:-1], 1.0, np.where(c[1:] < c[:-1], -1.0, 0.0))
    return float((signs * v[1:]).sum())


def calc_obv_slope(closes: list, volumes: list, window: int = 10) -> float:
    """
    Linear regression slope of OBV over last `window` bars.
    Positive = accumulation trend, negative = distribution.
    Returns 0.0 if insufficient data.
    """
    if len(closes) < window + 2:
        return 0.0
    c = np.array(closes, dtype=float)
    v = np.array(volumes, dtype=float)
    signs = np.where(c[1:] > c[:-1], 1.0, np.where(c[1:] < c[:-1], -1.0, 0.0))
    obv_series = np.cumsum(signs * v[1:])
    recent = obv_series[-window:]
    x = np.arange(len(recent), dtype=float)
    slope = np.polyfit(x, recent, 1)
    return float(slope[0])


def calc_volume_poc(closes: list, volumes: list, bins: int = 20) -> float:
    """
    Point of Control (POC): price level with highest volume in the provided window.
    Uses histogram binning across the closes range.
    Returns the mid-price of the highest-volume bin.
    Returns closes[-1] if insufficient data.
    """
    if len(closes) < 5 or len(volumes) < 5:
        return float(closes[-1]) if closes else 0.0
    c = np.array(closes, dtype=float)
    v = np.array(volumes, dtype=float)
    lo, hi = c.min(), c.max()
    if hi == lo:
        return float(c[-1])
    edges = np.linspace(lo, hi, bins + 1)
    vol_per_bin = np.zeros(bins)
    for price, vol in zip(c, v):
        idx = min(int((price - lo) / (hi - lo) * bins), bins - 1)
        vol_per_bin[idx] += vol
    poc_bin = int(np.argmax(vol_per_bin))
    poc_price = (edges[poc_bin] + edges[poc_bin + 1]) / 2
    return float(poc_price)


# ─────────────────────────────────────────────────────────────────────
# A2. TREND / MOMENTUM (TF-AGNOSTIC)
# ─────────────────────────────────────────────────────────────────────

def calc_ema(values: list, period: int) -> float:
    """
    EMA of last value. Pure Python/numpy implementation.
    Returns values[-1] if insufficient data.
    """
    if len(values) < period:
        return float(values[-1]) if values else 0.0
    v = np.array(values, dtype=float)
    k = 2.0 / (period + 1)
    ema = v[:period].mean()
    for price in v[period:]:
        ema = price * k + ema * (1 - k)
    return float(ema)


def calc_ema_spread(closes: list, fast: int = 8, slow: int = 21) -> float:
    """
    EMA fast - EMA slow, expressed as % of close.
    > 0 = bullish momentum, < 0 = bearish.
    """
    if len(closes) < slow:
        return 0.0
    fast_ema = calc_ema(closes, fast)
    slow_ema = calc_ema(closes, slow)
    ref = float(closes[-1]) if closes[-1] != 0 else slow_ema
    return float((fast_ema - slow_ema) / ref * 100) if ref else 0.0


def calc_adx(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    Average Directional Index (ADX).
    >= 25 = strong trend, 20-25 = weak trend, < 20 = no trend.
    Returns 0.0 if insufficient data (needs 2*period bars minimum).
    """
    min_bars = period * 2 + 1
    if len(closes) < min_bars:
        return 0.0
    h = np.array(highs[-min_bars:], dtype=float)
    l = np.array(lows[-min_bars:], dtype=float)
    c = np.array(closes[-min_bars:], dtype=float)

    tr_list, pdm_list, ndm_list = [], [], []
    for i in range(1, len(c)):
        tr = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
        pdm = max(h[i] - h[i-1], 0.0) if (h[i] - h[i-1]) > (l[i-1] - l[i]) else 0.0
        ndm = max(l[i-1] - l[i], 0.0) if (l[i-1] - l[i]) > (h[i] - h[i-1]) else 0.0
        tr_list.append(tr); pdm_list.append(pdm); ndm_list.append(ndm)

    def _smooth(arr, p):
        result = [sum(arr[:p])]
        for v in arr[p:]:
            result.append(result[-1] - result[-1] / p + v)
        return result

    atr_s  = _smooth(tr_list,  period)
    pdm_s  = _smooth(pdm_list, period)
    ndm_s  = _smooth(ndm_list, period)

    dx_list = []
    for atr_v, pdm_v, ndm_v in zip(atr_s, pdm_s, ndm_s):
        pdi = 100 * pdm_v / atr_v if atr_v else 0
        ndi = 100 * ndm_v / atr_v if atr_v else 0
        denom = pdi + ndi
        dx = 100 * abs(pdi - ndi) / denom if denom else 0
        dx_list.append(dx)

    if len(dx_list) < period:
        return 0.0
    adx = sum(dx_list[-period:]) / period
    return float(adx)


def calc_rsi(closes: list, period: int = 14) -> float:
    """
    RSI using Wilder's smoothing. Standard implementation.
    Returns 50.0 if insufficient data.
    """
    if len(closes) < period + 1:
        return 50.0
    c = np.array(closes[-(period * 3):], dtype=float)
    deltas = np.diff(c)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def calc_macd(closes: list,
              fast: int = 12, slow: int = 26, signal: int = 9
              ) -> tuple:
    """
    Returns (macd_line, signal_line, histogram).
    Needs at least slow + signal bars.
    Returns (0.0, 0.0, 0.0) if insufficient data.
    """
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    fast_ema  = calc_ema(closes, fast)
    slow_ema  = calc_ema(closes, slow)
    macd_line = fast_ema - slow_ema
    # Build a mini macd series for signal line smoothing
    # Use last (slow + signal * 3) bars to compute rolling macd
    window = min(len(closes), slow + signal * 3)
    c = np.array(closes[-window:], dtype=float)
    k_fast = 2.0 / (fast + 1)
    k_slow = 2.0 / (slow + 1)
    k_sig  = 2.0 / (signal + 1)
    ema_f = c[:fast].mean()
    ema_s = c[:slow].mean()
    for price in c[max(fast, slow):]:
        ema_f = price * k_fast + ema_f * (1 - k_fast)
        ema_s = price * k_slow + ema_s * (1 - k_slow)
    macd_line_v = ema_f - ema_s
    # Build signal from macd series over last signal*3 bars
    macd_series = []
    ef = c[:fast].mean(); es = c[:slow].mean()
    for price in c[slow:]:
        ef = price * k_fast + ef * (1 - k_fast)
        es = price * k_slow + es * (1 - k_slow)
        macd_series.append(ef - es)
    if len(macd_series) < signal:
        return float(macd_line_v), 0.0, float(macd_line_v)
    sig_line = sum(macd_series[:signal]) / signal
    for m in macd_series[signal:]:
        sig_line = m * k_sig + sig_line * (1 - k_sig)
    histogram = macd_line_v - sig_line
    return float(macd_line_v), float(sig_line), float(histogram)


def calc_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    Average True Range using Wilder's smoothing.
    Returns 0.0 if insufficient data.
    """
    if len(closes) < period + 1:
        return 0.0
    h = np.array(highs[-(period * 3):], dtype=float)
    l = np.array(lows[-(period * 3):], dtype=float)
    c = np.array(closes[-(period * 3):], dtype=float)
    trs = [max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
           for i in range(1, len(c))]
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return float(atr)


def calc_atr_pct(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    ATR as % of current close. Useful for normalising across assets.
    """
    atr = calc_atr(highs, lows, closes, period)
    close = float(closes[-1]) if closes else 1.0
    return float(atr / close * 100) if close else 0.0


def calc_bb_width(closes: list, period: int = 20, std_mult: float = 2.0) -> float:
    """
    Bollinger Band Width = (upper - lower) / middle, as %.
    High = high volatility/expansion, Low = squeeze/compression.
    Returns 0.0 if insufficient data.
    """
    if len(closes) < period:
        return 0.0
    c = np.array(closes[-period:], dtype=float)
    mid = c.mean()
    std = c.std()
    return float((std_mult * 2 * std) / mid * 100) if mid else 0.0


def calc_bb_pct(closes: list, period: int = 20, std_mult: float = 2.0) -> float:
    """
    %B: where current close sits within Bollinger Bands.
    0.0 = at lower band, 0.5 = at middle, 1.0 = at upper band.
    > 1.0 = above upper band, < 0.0 = below lower band.
    """
    if len(closes) < period:
        return 0.5
    c = np.array(closes[-period:], dtype=float)
    mid = c.mean()
    std = c.std()
    if std == 0:
        return 0.5
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return float((closes[-1] - lower) / (upper - lower))


def calc_stoch_rsi(closes: list, rsi_period: int = 14,
                   stoch_period: int = 14, smooth_k: int = 3) -> tuple:
    """
    Stochastic RSI → returns (%K, %D).
    %K: StochRSI smoothed, %D: signal of %K.
    Returns (50.0, 50.0) if insufficient data.
    Needs rsi_period + stoch_period + smooth_k bars minimum.
    """
    min_bars = rsi_period + stoch_period + smooth_k + 5
    if len(closes) < min_bars:
        return 50.0, 50.0
    # Build RSI series
    rsi_series = []
    for i in range(rsi_period + 1, len(closes) + 1):
        rsi_series.append(calc_rsi(closes[:i], rsi_period))
    if len(rsi_series) < stoch_period + smooth_k:
        return 50.0, 50.0
    # StochRSI raw
    stoch_raw = []
    for i in range(stoch_period, len(rsi_series) + 1):
        window = rsi_series[i - stoch_period:i]
        lo, hi = min(window), max(window)
        val = (rsi_series[i-1] - lo) / (hi - lo) * 100 if hi != lo else 50.0
        stoch_raw.append(val)
    # Smooth K
    k_series = []
    for i in range(smooth_k, len(stoch_raw) + 1):
        k_series.append(sum(stoch_raw[i - smooth_k:i]) / smooth_k)
    if not k_series:
        return 50.0, 50.0
    # D = SMA(K, 3)
    d_val = sum(k_series[-3:]) / min(3, len(k_series))
    return float(k_series[-1]), float(d_val)


def calc_cmf(highs: list, lows: list, closes: list,
             volumes: list, period: int = 20) -> float:
    """
    Chaikin Money Flow. Range: -1.0 to +1.0.
    > 0.05 = buying pressure, < -0.05 = selling pressure.
    Returns 0.0 if insufficient data.
    """
    if len(closes) < period:
        return 0.0
    h = np.array(highs[-period:], dtype=float)
    l = np.array(lows[-period:], dtype=float)
    c = np.array(closes[-period:], dtype=float)
    v = np.array(volumes[-period:], dtype=float)
    hl_range = h - l
    mfv = np.where(hl_range > 0,
                   ((c - l) - (h - c)) / hl_range * v,
                   0.0)
    total_v = v.sum()
    return float(mfv.sum() / total_v) if total_v else 0.0


# ─────────────────────────────────────────────────────────────────────
# A3. CRYPTO-NATIVE INDICATORS
# ─────────────────────────────────────────────────────────────────────

def calc_funding_zscore(funding_history: list) -> float:
    """
    Z-score of most recent funding rate vs history.
    Extreme values (|z| > 2) = potential reversion opportunity.
    Returns 0.0 if fewer than 3 data points.
    """
    if len(funding_history) < 3:
        return 0.0
    arr = np.array(funding_history, dtype=float)
    mu = arr[:-1].mean()
    sigma = arr[:-1].std()
    return float((arr[-1] - mu) / sigma) if sigma > 0 else 0.0


def calc_oi_momentum(oi_history: list, period: int = 5) -> float:
    """
    OI momentum = (OI[-1] - OI[-period]) / OI[-period] * 100.
    Positive = OI expanding (new money in), negative = OI contracting (closing).
    OI rising + price rising = trend continuation (strong).
    OI rising + price falling = bearish continuation (shorts piling in).
    Returns 0.0 if insufficient data.
    """
    if len(oi_history) < period + 1:
        return 0.0
    base = float(oi_history[-period - 1])
    current = float(oi_history[-1])
    return float((current - base) / base * 100) if base else 0.0


def calc_bid_ask_imbalance(bid_levels: list, ask_levels: list,
                           top_n: int = 10) -> float:
    """
    Orderbook imbalance from top N price levels.
    bid_levels / ask_levels: list of (price, size) tuples.
    Returns: -1.0 (pure ask) to +1.0 (pure bid).
    """
    bid_sz = sum(sz for _, sz in bid_levels[:top_n])
    ask_sz = sum(sz for _, sz in ask_levels[:top_n])
    total = bid_sz + ask_sz
    return float((bid_sz - ask_sz) / total) if total else 0.0


def calc_price_vs_prev_day(close: float, prev_day_px: float) -> float:
    """
    % change vs previous day close. Simple but useful for intraday context.
    Returns 0.0 if prev_day_px is 0.
    """
    if prev_day_px == 0:
        return 0.0
    return float((close - prev_day_px) / prev_day_px * 100)


def calc_spread_bps(best_bid: float, best_ask: float) -> float:
    """
    Bid-ask spread in basis points. Mid = (bid+ask)/2.
    High spread → low liquidity → avoid taker entries.
    Returns 0.0 if inputs invalid.
    """
    if best_bid <= 0 or best_ask <= 0:
        return 0.0
    mid = (best_bid + best_ask) / 2
    return float((best_ask - best_bid) / mid * 10000) if mid else 0.0


# ─────────────────────────────────────────────────────────────────────
# A4. CANDLESTICK PATTERN RECOGNITION
# ─────────────────────────────────────────────────────────────────────

def calc_candle_patterns(opens: list, highs: list, lows: list, closes: list) -> Dict[str, float]:
    """
    Recognize candlestick patterns on the most recent bars.
    Returns a dict with 1.0 (pattern present) or 0.0 (absent).
    Supported: hammer, shooting_star, bull_engulfing, bear_engulfing, inside_bar, doji, pinbar.
    """
    out = {
        "hammer": 0.0, "shooting_star": 0.0, "bull_engulfing": 0.0,
        "bear_engulfing": 0.0, "inside_bar": 0.0, "doji": 0.0, "pinbar": 0.0
    }
    if len(closes) < 2:
        return out
    
    o = np.array(opens[-2:], dtype=float)
    h = np.array(highs[-2:], dtype=float)
    l = np.array(lows[-2:], dtype=float)
    c = np.array(closes[-2:], dtype=float)

    # Current bar metrics
    body = abs(c[1] - o[1])
    range_bar = h[1] - l[1]
    if range_bar == 0:
        return out

    # Shadows
    lower_shadow = min(c[1], o[1]) - l[1]
    upper_shadow = h[1] - max(c[1], o[1])

    # 1. Doji (extremely small body)
    if body <= range_bar * 0.10:
        out["doji"] = 1.0

    # 2. Hammer (long lower shadow, small body near top)
    if lower_shadow > body * 2.0 and upper_shadow < range_bar * 0.15:
        out["hammer"] = 1.0

    # 3. Shooting Star (long upper shadow, small body near bottom)
    if upper_shadow > body * 2.0 and lower_shadow < range_bar * 0.15:
        out["shooting_star"] = 1.0

    # 4. Bullish Engulfing
    if c[0] < o[0] and c[1] > o[1] and c[1] >= o[0] and o[1] <= c[0]:
        out["bull_engulfing"] = 1.0

    # 5. Bearish Engulfing
    if c[0] > o[0] and c[1] < o[1] and c[1] <= o[0] and o[1] >= c[0]:
        out["bear_engulfing"] = 1.0

    # 6. Inside Bar
    if h[1] < h[0] and l[1] > l[0]:
        out["inside_bar"] = 1.0

    # 7. Pinbar
    is_bull_pin = (lower_shadow > range_bar * 0.60) and (body < range_bar * 0.35)
    is_bear_pin = (upper_shadow > range_bar * 0.60) and (body < range_bar * 0.35)
    if is_bull_pin or is_bear_pin:
        out["pinbar"] = 1.0

    return out


# ─────────────────────────────────────────────────────────────────────
# A5. ADVANCED VOLATILITY & CHANNELS
# ─────────────────────────────────────────────────────────────────────

def calc_parkinson_volatility(highs: list, lows: list, period: int = 20) -> float:
    """
    Parkinson Volatility based on High/Low range.
    """
    if len(highs) < period:
        return 0.0
    h = np.array(highs[-period:], dtype=float)
    l = np.array(lows[-period:], dtype=float)
    if (l <= 0).any():
        return 0.0
    # log(h/l)^2
    log_ratio_sq = np.log(h / l) ** 2
    vol = np.sqrt(log_ratio_sq.sum() / (4.0 * np.log(2.0) * period))
    return float(vol)


def calc_keltner_channels(highs: list, lows: list, closes: list,
                          ema_period: int = 20, atr_period: int = 10,
                          multiplier: float = 2.0) -> Dict[str, float]:
    """
    Keltner Channels: EMA of closes ± multiplier * ATR.
    """
    if len(closes) < max(ema_period, atr_period):
        return {"kc_mid": 0.0, "kc_upper": 0.0, "kc_lower": 0.0}
    
    mid = calc_ema(closes, ema_period)
    atr = calc_atr(highs, lows, closes, atr_period)
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr
    return {"kc_mid": mid, "kc_upper": upper, "kc_lower": lower}


def calc_cmo(closes: list, period: int = 9) -> float:
    """
    Chande Momentum Oscillator (CMO).
    """
    if len(closes) < period + 1:
        return 0.0
    c = np.array(closes[-period-1:], dtype=float)
    deltas = np.diff(c)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    sum_g = gains.sum()
    sum_l = losses.sum()
    denom = sum_g + sum_l
    return float((sum_g - sum_l) / denom * 100) if denom else 0.0


# ─────────────────────────────────────────────────────────────────────
# A6. NEW TREND / MOMENTUM
# ─────────────────────────────────────────────────────────────────────

def calc_supertrend(highs: list, lows: list, closes: list,
                    period: int = 10, multiplier: float = 3.0) -> tuple[float, float]:
    """
    SuperTrend indicator. Returns (supertrend_value, direction).
    direction: 1.0 (bullish), -1.0 (bearish).
    """
    if len(closes) < period + 1:
        return float(closes[-1]) if closes else 0.0, 1.0

    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)
    n = c.size

    # True Range
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
    
    # ATR Wilder smoothing
    atr = np.zeros(n)
    atr[period] = tr[1:period+1].mean()
    for i in range(period + 1, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    hl2 = (h + l) / 2
    basic_ub = hl2 + multiplier * atr
    basic_lb = hl2 - multiplier * atr

    final_ub = np.zeros(n)
    final_lb = np.zeros(n)
    st = np.zeros(n)
    dir_arr = np.zeros(n)

    dir_arr[period] = 1.0
    st[period] = basic_ub[period]

    for i in range(period + 1, n):
        # Upper band adjustment
        if basic_ub[i] < final_ub[i-1] or c[i-1] > final_ub[i-1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i-1]

        # Lower band adjustment
        if basic_lb[i] > final_lb[i-1] or c[i-1] < final_lb[i-1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i-1]

        # Direction calculation
        if st[i-1] == final_ub[i-1]:
            dir_arr[i] = -1.0 if c[i] <= final_ub[i] else 1.0
        else:
            dir_arr[i] = 1.0 if c[i] >= final_lb[i] else -1.0

        st[i] = final_ub[i] if dir_arr[i] == -1.0 else final_lb[i]

    return float(st[-1]), float(dir_arr[-1])


def calc_stochastic_oscillator(highs: list, lows: list, closes: list,
                              k_period: int = 14, d_period: int = 3) -> tuple[float, float]:
    """
    Stochastic Oscillator (%K, %D).
    """
    if len(closes) < k_period + d_period:
        return 50.0, 50.0
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)

    # %K series
    k_vals = []
    for i in range(len(c) - d_period - 2, len(c)):
        start_idx = max(0, i - k_period + 1)
        sub_h = h[start_idx:i + 1]
        sub_l = l[start_idx:i + 1]
        sub_c = c[i]
        highest_h = sub_h.max() if len(sub_h) > 0 else sub_c
        lowest_l = sub_l.min() if len(sub_l) > 0 else sub_c
        denom = highest_h - lowest_l
        k_val = (sub_c - lowest_l) / denom * 100 if denom else 50.0
        k_vals.append(k_val)

    # %D is SMA of %K
    k = k_vals[-1]
    d = sum(k_vals[-d_period:]) / d_period
    return float(k), float(d)


def calc_cci(highs: list, lows: list, closes: list, period: int = 20) -> float:
    """
    Commodity Channel Index (CCI).
    """
    if len(closes) < period:
        return 0.0
    h = np.array(highs[-period:], dtype=float)
    l = np.array(lows[-period:], dtype=float)
    c = np.array(closes[-period:], dtype=float)
    
    tp = (h + l + c) / 3
    sma_tp = tp.mean()
    mean_dev = np.abs(tp - sma_tp).mean()
    if mean_dev == 0:
        return 0.0
    cci = (tp[-1] - sma_tp) / (0.015 * mean_dev)
    return float(cci)


# ─────────────────────────────────────────────────────────────────────
# A7. NEW VOLUME INDICATORS
# ─────────────────────────────────────────────────────────────────────

def calc_mfi(highs: list, lows: list, closes: list, volumes: list, period: int = 14) -> float:
    """
    Money Flow Index (MFI).
    """
    if len(closes) < period + 1:
        return 50.0
    h = np.array(highs[-period-1:], dtype=float)
    l = np.array(lows[-period-1:], dtype=float)
    c = np.array(closes[-period-1:], dtype=float)
    v = np.array(volumes[-period-1:], dtype=float)

    tp = (h + l + c) / 3
    rmf = tp * v

    pos_flow = 0.0
    neg_flow = 0.0
    for i in range(1, len(tp)):
        if tp[i] > tp[i-1]:
            pos_flow += rmf[i]
        elif tp[i] < tp[i-1]:
            neg_flow += rmf[i]

    if neg_flow == 0:
        return 100.0 if pos_flow > 0 else 50.0
    mfr = pos_flow / neg_flow
    return float(100.0 - 100.0 / (1.0 + mfr))


def calc_ease_of_movement(highs: list, lows: list, volumes: list, period: int = 14) -> float:
    """
    Ease of Movement (EMV) smoothed.
    """
    if len(highs) < period + 1:
        return 0.0
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    v = np.array(volumes, dtype=float)
    
    hl2 = (h + l) / 2
    dm = hl2[1:] - hl2[:-1]
    box_ratio = (v[1:] / 100000000.0) / (h[1:] - l[1:])
    emv_raw = np.where(h[1:] - l[1:] > 0, dm / box_ratio, 0.0)
    
    # Return smoothed EMV (SMA of raw EMV)
    if len(emv_raw) < period:
        return 0.0
    return float(emv_raw[-period:].mean())


def calc_volume_profile_va(closes: list, volumes: list, bins: int = 20,
                           value_area_pct: float = 0.70) -> Dict[str, float]:
    """
    Calculate Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL).
    """
    out = {"poc": 0.0, "vah": 0.0, "val": 0.0}
    if len(closes) < 10:
        val = float(closes[-1]) if closes else 0.0
        return {"poc": val, "vah": val, "val": val}

    c = np.array(closes, dtype=float)
    v = np.array(volumes, dtype=float)
    lo, hi = c.min(), c.max()
    if hi == lo:
        return {"poc": lo, "vah": lo, "val": lo}

    edges = np.linspace(lo, hi, bins + 1)
    bin_vols = np.zeros(bins)
    for price, vol in zip(c, v):
        idx = min(int((price - lo) / (hi - lo) * bins), bins - 1)
        bin_vols[idx] += vol

    # 1. Find POC (bin with highest volume)
    poc_idx = int(np.argmax(bin_vols))
    poc_price = (edges[poc_idx] + edges[poc_idx + 1]) / 2
    out["poc"] = float(poc_price)

    # 2. Grow Value Area around POC
    total_vol = bin_vols.sum()
    target_vol = total_vol * value_area_pct
    current_vol = bin_vols[poc_idx]

    left_idx = poc_idx
    right_idx = poc_idx

    while current_vol < target_vol:
        # volume to add on the left side
        left_vol = bin_vols[left_idx - 1] if left_idx > 0 else 0
        # volume to add on the right side
        right_vol = bin_vols[right_idx + 1] if right_idx < bins - 1 else 0

        if left_vol == 0 and right_vol == 0:
            break

        if left_vol >= right_vol:
            left_idx -= 1
            current_vol += left_vol
        else:
            right_idx += 1
            current_vol += right_vol

    out["val"] = float(edges[left_idx])
    out["vah"] = float(edges[right_idx + 1])
    return out


# ── CVD Slope & Decayed OFI/TFI ──────────────────────────────────
def calc_cvd_slope(prices: List[float], sizes: List[float], sides: List[str], window: int = 20) -> float:
    """
    Calculates the linear regression slope of CVD over a specified rolling window of trades.
    """
    if len(sizes) < window or len(sides) < window:
        return 0.0
    
    sz = np.asarray(sizes, dtype=np.float64)
    sd = sides
    signs = np.where(np.array(sd) == "B", 1.0, np.where(np.array(sd) == "A", -1.0, 0.0))
    cvd_ticks = np.cumsum(sz * signs)
    
    y = cvd_ticks[-window:]
    x = np.arange(window, dtype=np.float64)
    
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    if denominator == 0.0:
        return 0.0
    return float(numerator / denominator)


def calc_decayed_flow_imbalance(sizes: List[float], sides: List[str], window: int = 20, lambda_val: float = 0.05) -> float:
    """
    Calculates exponentially time-decayed Trade Flow Imbalance.
    """
    if len(sizes) < window or len(sides) < window:
        return 0.0
    sz = np.asarray(sizes[-window:], dtype=np.float64)
    sd = sides[-window:]
    signs = np.where(np.array(sd) == "B", 1.0, np.where(np.array(sd) == "A", -1.0, 0.0))
    
    weights = np.exp(-lambda_val * np.arange(window)[::-1])
    weighted_delta = sz * signs * weights
    total_weighted = np.sum(sz * weights)
    
    return float(np.sum(weighted_delta) / total_weighted) if total_weighted else 0.0


def calc_bb_percentile(bb_widths: List[float], window: int = 30) -> float:
    """
    Maps the current Bollinger Band width to its rolling percentile (0-100) over the last window intervals.
    """
    if len(bb_widths) < 2:
        return 50.0
    current = bb_widths[-1]
    lookback = bb_widths[-window:]
    arr = np.asarray(lookback, dtype=np.float64)
    min_val = np.min(arr)
    max_val = np.max(arr)
    if max_val == min_val:
        return 50.0
    return float(np.sum(arr <= current) / len(arr) * 100.0)

