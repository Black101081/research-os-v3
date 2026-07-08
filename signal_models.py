from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────
# Signal direction and family enums (strings, not Enum, for JSON compat)
# ─────────────────────────────────────────────────────────────────────

DIRECTION_LONG  = "long"
DIRECTION_SHORT = "short"
DIRECTION_BOTH  = "both"    # for symmetric setups (e.g. volatility breakout)

FAMILY_ORDER_FLOW        = "order_flow"
FAMILY_BREAKOUT          = "breakout"
FAMILY_MEAN_REVERSION    = "mean_reversion"
FAMILY_CONTINUATION      = "continuation"
FAMILY_DIVERGENCE        = "divergence"
FAMILY_VOLATILITY_EVENT  = "volatility_event"
FAMILY_FUNDING_REVERSION = "funding_reversion"
FAMILY_OI_REVERSAL       = "oi_reversal"

# The 18 Specific Strategy Families
FAMILY_MACD_CONTINUATION          = "macd_trend_continuation"
FAMILY_EMA_PULLBACK_BUY            = "ema_pullback_buy"
FAMILY_OBV_ACCUMULATION            = "obv_accumulation_breakout"
FAMILY_HIGH_VOL_BREAKOUT           = "high_vol_breakout"
FAMILY_MOMENTUM_CHASING            = "momentum_chasing"
FAMILY_VWAP_REVERSION_FADE         = "vwap_reversion_fade"
FAMILY_RANGE_BOUNDARY_FADE         = "range_boundary_fade"
FAMILY_LIQUIDITY_SWEEP             = "liquidity_sweep_hunt"
FAMILY_HFT_ORDER_FLOW              = "hft_order_flow_momentum"
FAMILY_HIGH_VOL_BREAKDOWN          = "high_vol_breakdown"
FAMILY_SHORT_MOMENTUM              = "short_momentum_chase"
FAMILY_OVERSOLD_BOUNCE             = "oversold_bounce"
FAMILY_BEAR_TREND_CONTINUATION     = "bearish_trend_continuation"
FAMILY_EMA_PULLBACK_SELL           = "ema_pullback_sell"
FAMILY_OBV_DISTRIBUTION            = "obv_distribution_breakdown"
FAMILY_MEAN_REVERSION_SQUEEZE      = "mean_reversion_squeeze"

# All valid families — used for validation
ALL_FAMILIES = {
    FAMILY_ORDER_FLOW, FAMILY_BREAKOUT, FAMILY_MEAN_REVERSION,
    FAMILY_CONTINUATION, FAMILY_DIVERGENCE, FAMILY_VOLATILITY_EVENT,
    FAMILY_FUNDING_REVERSION, FAMILY_OI_REVERSAL,
    FAMILY_MACD_CONTINUATION, FAMILY_EMA_PULLBACK_BUY, FAMILY_OBV_ACCUMULATION,
    FAMILY_HIGH_VOL_BREAKOUT, FAMILY_MOMENTUM_CHASING, FAMILY_VWAP_REVERSION_FADE,
    FAMILY_RANGE_BOUNDARY_FADE, FAMILY_LIQUIDITY_SWEEP, FAMILY_HFT_ORDER_FLOW,
    FAMILY_HIGH_VOL_BREAKDOWN, FAMILY_SHORT_MOMENTUM, FAMILY_OVERSOLD_BOUNCE,
    FAMILY_BEAR_TREND_CONTINUATION, FAMILY_EMA_PULLBACK_SELL, FAMILY_OBV_DISTRIBUTION,
    FAMILY_MEAN_REVERSION_SQUEEZE
}


# ─────────────────────────────────────────────────────────────────────
# Core signal result
# ─────────────────────────────────────────────────────────────────────

@dataclass
class SignalResult:
    """
    Unified output of every signal function in signal_library.py.
    downstream consumers (paper_broker, risk_engine) should read ONLY
    this struct — never raw indicators.
    """

    # Identity
    signal_id: str                  # "{symbol}_{family}_{interval}_{ts_short}"
    symbol: str
    family: str                     # one of ALL_FAMILIES
    interval: str                   # "5m", "15m", etc.
    asset_role: str                 # "anchor" | "major" | "alt"

    # Decision
    fired: bool                     # True = actionable signal
    direction: str                  # DIRECTION_LONG | DIRECTION_SHORT | DIRECTION_BOTH

    # Price levels (0.0 = not computed / signal not fired)
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    take_profit_2: float = 0.0      # optional second TP (2R target)

    # Quality
    confidence_score: float = 0.0  # 0.0–1.0
    confluence_votes: int = 0       # raw vote count
    confluence_total: int = 0       # max possible votes for this signal

    # Risk/reward
    risk_reward_ratio: float = 0.0  # |TP - entry| / |entry - SL|, 0 if SL==entry

    # Context at fire time (for logging / research)
    atr_at_signal: float = 0.0
    htf_bias: str = "neutral"       # from MultiTFSymbolState.htf_bias()
    mtf_alignment: float = 0.0      # from MultiTFSymbolState.mtf_alignment()
    funding_signal: float = 0.0     # -1 / 0 / +1 from tf_state.indicators
    volume_quality_score: float = 0.0

    # Invalidation
    invalidation_price: float = 0.0  # signal void if price crosses this
    invalidation_reason: str = ""    # human-readable

    # Metadata
    fired_at: str = field(default_factory=_now_iso)
    indicators_snapshot: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)   # debug/confluence notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "family": self.family,
            "interval": self.interval,
            "asset_role": self.asset_role,
            "fired": self.fired,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "take_profit_2": self.take_profit_2,
            "confidence_score": round(self.confidence_score, 4),
            "confluence_votes": self.confluence_votes,
            "confluence_total": self.confluence_total,
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "atr_at_signal": self.atr_at_signal,
            "htf_bias": self.htf_bias,
            "mtf_alignment": round(self.mtf_alignment, 3),
            "funding_signal": self.funding_signal,
            "volume_quality_score": round(self.volume_quality_score, 3),
            "invalidation_price": self.invalidation_price,
            "invalidation_reason": self.invalidation_reason,
            "fired_at": self.fired_at,
            "notes": self.notes,
        }


@dataclass
class SignalBatch:
    """All signals fired in one evaluation cycle for one symbol."""
    symbol: str
    interval: str
    evaluated_at: str = field(default_factory=_now_iso)
    results: List[SignalResult] = field(default_factory=list)

    def fired_signals(self) -> List[SignalResult]:
        return [r for r in self.results if r.fired]

    def best_signal(self) -> Optional[SignalResult]:
        fired = self.fired_signals()
        if not fired:
            return None
        return max(fired, key=lambda s: s.confidence_score)
