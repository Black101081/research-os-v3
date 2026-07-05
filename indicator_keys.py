"""
indicator_keys.py — Single source of truth for all thresholds and indicator constants.

All modules that need threshold values MUST import from here.
Never hardcode these values in business logic.
"""
from __future__ import annotations

# ── Bollinger Bands ──────────────────────────────────────────────
BOLLINGER_SQUEEZE_THRESHOLD = 0.15       # BollingerWidth <= this = squeeze active
BOLLINGER_SQUEEZE_STRONG = 0.08         # Tighter squeeze — higher conviction
BOLLINGER_PERIOD = 20
BOLLINGER_NUM_STD = 2.0

# ── Z-Score ──────────────────────────────────────────────────────
ZSCORE_ENTRY_LONG_THRESHOLD = -1.5      # Z <= this = long entry for mean reversion
ZSCORE_ENTRY_SHORT_THRESHOLD = 1.5     # Z >= this = short entry for mean reversion
ZSCORE_ENTRY_STRONG = 2.0              # Stronger signal threshold
ZSCORE_EXIT_THRESHOLD = -0.2           # Z back near center = exit
ZSCORE_PERIOD = 20
ZSCORE_PERIOD_LONG = 50

# ── MACD ─────────────────────────────────────────────────────────
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL_PERIOD = 9

# ── RSI ──────────────────────────────────────────────────────────
RSI_PERIOD = 14
RSI_FAST_PERIOD = 7
RSI_OVERSOLD = 30
RSI_OVERSOLD_STRONG = 20
RSI_OVERBOUGHT = 70
RSI_OVERBOUGHT_STRONG = 80

# ── Volume ───────────────────────────────────────────────────────
REL_VOLUME_MIN = 1.0                   # Minimum relative volume for confirmation
REL_VOLUME_SURGE = 2.0                 # Volume surge threshold
REL_VOLUME_EXTREME = 3.0              # Extreme volume anomaly
VOLUME_PERIOD = 20

# ── ATR ──────────────────────────────────────────────────────────
ATR_PERIOD = 14

# ── Stochastic ───────────────────────────────────────────────────
STOCH_PERIOD = 14
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

# ── Williams %R ──────────────────────────────────────────────────
WILLIAMS_R_PERIOD = 14
WILLIAMS_R_OVERSOLD = -80
WILLIAMS_R_OVERBOUGHT = -20

# ── Flow Imbalance ───────────────────────────────────────────────
FLOW_IMBALANCE_THRESHOLD = 0.3         # Significant directional imbalance
FLOW_IMBALANCE_STRONG = 0.5           # Strong imbalance
FLOW_WINDOW_SHORT = 20
FLOW_WINDOW_LONG = 50

# ── Microstructure ───────────────────────────────────────────────
SPREAD_BPS_MAX = 10.0                  # Above this = too expensive to trade
MICRO_VOL_HIGH = 0.005                 # High intrabar volatility threshold

# ── Regime ───────────────────────────────────────────────────────
VOL_EXPANSION_RATIO = 1.5              # volatility_ratio_5_20 above this = vol expanding
RET_5_TREND_THRESHOLD = 0.015          # |ret_5| above this = directional trend
VOL_20_HIGH_THRESHOLD = 0.03           # volatility_20 above this = high vol regime

# ── Cross-Asset ──────────────────────────────────────────────────
BTC_STRONG_MOVE_THRESHOLD = 0.003      # btc_ret_1 abs > this = significant BTC move
CORRELATION_HIGH = 0.7                 # market_correlation_20 above this = beta-driven

# ── Pattern ──────────────────────────────────────────────────────
PIN_BAR_RATIO_MIN = 3.0                # wick/body >= this = valid pin bar
CONSECUTIVE_BARS_EXHAUSTION = 4       # >= this many same-direction bars = exhaustion

# ── EMA Periods ──────────────────────────────────────────────────
EMA_FAST = 8
EMA_MED = 21
EMA_SLOW = 55
SMA_20 = 20
SMA_50 = 50
