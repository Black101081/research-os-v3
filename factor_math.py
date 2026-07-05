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
