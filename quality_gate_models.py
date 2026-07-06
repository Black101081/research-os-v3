from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────
# Layer 1 config — Session / Time filter
# ─────────────────────────────────────────────────────────────────────

@dataclass
class SessionConfig:
    """
    Trading session windows in UTC hours.
    Signals outside ALL active sessions are blocked.
    Each window = (start_hour_utc, end_hour_utc), inclusive.
    """
    enabled: bool = True

    # Primary liquid sessions (UTC)
    sessions: List[Tuple[int, int]] = field(default_factory=lambda: [
        (1,  9),    # Asia: Tokyo/Singapore (01:00–09:00 UTC)
        (7,  16),   # London (07:00–16:00 UTC)
        (13, 22),   # New York (13:00–22:00 UTC)
    ])

    # Dead zones — always block regardless of session config
    # Crypto: Sunday 22:00 UTC - Monday 00:30 UTC (weekly close gap)
    dead_zones: List[Tuple[int, int]] = field(default_factory=lambda: [
        (22, 24),   # 22:00–00:00 UTC daily low-liquidity
        (0,  1),    # 00:00–01:00 UTC daily low-liquidity
    ])

    # Minimum session overlap hours required for signal to pass
    min_session_hours_remaining: float = 1.0

    # Block signals in final N minutes before session close
    block_near_session_end_minutes: int = 15


# ─────────────────────────────────────────────────────────────────────
# Layer 2 config — Market Regime filter
# ─────────────────────────────────────────────────────────────────────

@dataclass
class RegimeConfig:
    """
    Market regime classification thresholds.
    Regime is computed from the anchor asset (BTC) on the reference TF.
    """
    enabled: bool = True
    anchor_symbol: str = "BTC"
    reference_interval: str = "1h"   # TF used to classify regime

    # ADX thresholds
    adx_trending_min: float = 25.0   # ADX >= 25 = trending regime
    adx_choppy_max:   float = 20.0   # ADX < 20  = choppy regime

    # Regime rules per signal family
    # "trend_only"      = only allowed in trending regime
    # "range_only"      = only allowed in choppy/ranging regime
    # "any"             = allowed in any regime
    family_regime_map: Dict[str, str] = field(default_factory=lambda: {
        "continuation":      "trend_only",
        "breakout":          "trend_only",
        "divergence":        "any",
        "mean_reversion":    "range_only",
        "order_flow":        "any",
        "volatility_event":  "any",
        "funding_reversion": "any",
        "oi_reversal":       "any",
    })

    # BTC structure bias: if BTC is in bear structure,
    # block ALL new long signals on correlated assets
    enable_btc_structure_bias: bool = True
    btc_bear_ema_threshold: float = -0.5   # ema_spread_8_21 < threshold = bear
    btc_bull_ema_threshold: float = 0.5    # ema_spread_8_21 > threshold = bull


# ─────────────────────────────────────────────────────────────────────
# Layer 3 config — Correlation / Portfolio heat
# ─────────────────────────────────────────────────────────────────────

@dataclass
class PortfolioConfig:
    """
    Portfolio-level constraints before accepting a new signal.
    """
    enabled: bool = True

    # Max simultaneous open signals (all symbols combined)
    max_concurrent_signals: int = 4

    # Max signals from same correlation cluster
    # Cluster mapping: symbol → cluster_id
    # Symbols in same cluster = highly correlated
    correlation_clusters: Dict[str, str] = field(default_factory=lambda: {
        "BTC":  "crypto_majors",
        "ETH":  "crypto_majors",
        "SOL":  "crypto_majors",
        "BNB":  "crypto_majors",
        "AVAX": "crypto_majors",
        "MATIC":"crypto_majors",
        "ARB":  "crypto_l2",
        "OP":   "crypto_l2",
    })
    max_signals_per_cluster: int = 2

    # Max portfolio heat (sum of risk per trade as % of total capital)
    # Each signal consumes: position_size_pct * 1.0 of heat
    max_portfolio_heat_pct: float = 6.0    # 6% total capital at risk

    # Cooldown per (symbol, family, direction) in seconds
    # Prevents re-entry into same setup too quickly
    cooldown_seconds: int = 300   # 5 minutes default


# ─────────────────────────────────────────────────────────────────────
# Layer 4 config — Statistical validity / EV gate
# ─────────────────────────────────────────────────────────────────────

@dataclass
class StatisticalConfig:
    """
    Expected value filter based on historical win rates per signal family.
    EV = win_rate * avg_reward - (1 - win_rate) * avg_risk
    Signal passes if EV > min_ev_threshold.
    """
    enabled: bool = True

    # Historical win rates per signal family (configurable, not hardcoded)
    # These should be updated from backtesting / live trading results
    family_win_rates: Dict[str, float] = field(default_factory=lambda: {
        "continuation":      0.52,
        "breakout":          0.48,
        "divergence":        0.50,
        "mean_reversion":    0.58,
        "order_flow":        0.54,
        "volatility_event":  0.45,
        "funding_reversion": 0.55,
        "oi_reversal":       0.50,
    })

    # Minimum positive EV required (in R, where R = 1 risk unit)
    min_ev_r: float = 0.05   # EV must be > 0.05R to pass

    # Minimum confidence score (from signal_library)
    min_confidence: float = 0.50

    # Minimum risk:reward ratio
    min_rr_ratio: float = 1.5

    # Confidence boost per additional confluence vote above minimum
    confidence_boost_per_vote: float = 0.05


# ─────────────────────────────────────────────────────────────────────
# Layer 5 config — Position sizing
# ─────────────────────────────────────────────────────────────────────

@dataclass
class SizingConfig:
    """
    Kelly-fraction position sizing based on signal quality.
    Position size = f* * account_equity, where f* is Kelly fraction.
    Half-Kelly is used by default for safety.
    """
    enabled: bool = True

    account_equity: float = 10_000.0   # USD, updated externally

    # Kelly fraction multiplier (0.5 = half-Kelly)
    kelly_fraction: float = 0.5

    # Absolute limits regardless of Kelly output
    min_position_pct: float = 0.5      # 0.5% minimum
    max_position_pct: float = 5.0      # 5.0% maximum per signal

    # Scale down for lower-confidence signals
    confidence_to_size_map: Dict[str, float] = field(default_factory=lambda: {
        "0.50": 0.5,    # confidence 0.50–0.59 → 50% of max size
        "0.60": 0.65,
        "0.70": 0.80,
        "0.80": 0.90,
        "0.90": 1.00,   # confidence >= 0.90 → full size
    })

    # Asset-role size multipliers
    role_size_multiplier: Dict[str, float] = field(default_factory=lambda: {
        "anchor": 1.0,    # BTC: full size
        "major":  0.75,   # ETH, SOL: 75%
        "alt":    0.50,   # everything else: 50%
    })


# ─────────────────────────────────────────────────────────────────────
# Master config
# ─────────────────────────────────────────────────────────────────────

@dataclass
class QualityGateConfig:
    session:     SessionConfig     = field(default_factory=SessionConfig)
    regime:      RegimeConfig      = field(default_factory=RegimeConfig)
    portfolio:   PortfolioConfig   = field(default_factory=PortfolioConfig)
    statistical: StatisticalConfig = field(default_factory=StatisticalConfig)
    sizing:      SizingConfig      = field(default_factory=SizingConfig)

    # Global kill-switch: False = gate disabled entirely (for testing)
    enabled: bool = True


# ─────────────────────────────────────────────────────────────────────
# Output structures
# ─────────────────────────────────────────────────────────────────────

GATE_PASS  = "pass"
GATE_BLOCK = "block"

BLOCK_REASON_SESSION     = "session_filter"
BLOCK_REASON_REGIME      = "regime_filter"
BLOCK_REASON_PORTFOLIO   = "portfolio_filter"
BLOCK_REASON_STATISTICAL = "statistical_filter"
BLOCK_REASON_COOLDOWN    = "cooldown_filter"
BLOCK_REASON_DISABLED    = "gate_disabled"


@dataclass
class LayerResult:
    """Result of a single gate layer evaluation."""
    layer_name: str
    verdict: str        # GATE_PASS or GATE_BLOCK
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualifiedSignal:
    """
    A SignalResult that has passed all 5 quality gate layers,
    enriched with position sizing and regime context.
    """
    # Original signal (from signal_library.py)
    signal: Any   # SignalResult — avoid circular import

    # Quality gate output
    verdict: str = GATE_PASS    # always GATE_PASS for QualifiedSignal
    layer_results: List[LayerResult] = field(default_factory=list)

    # Position sizing output
    position_size_pct: float = 0.0    # % of account equity
    position_size_usd: float = 0.0    # absolute USD size
    risk_amount_usd: float = 0.0      # USD at risk (position_size * SL distance %)

    # Regime context at qualification time
    market_regime: str = "unknown"    # "trending" | "choppy" | "unknown"
    btc_structure: str = "neutral"    # "bullish" | "bearish" | "neutral"
    session_name: str = "unknown"     # "asia" | "london" | "new_york" | "overlap"

    # EV calculation
    expected_value_r: float = 0.0     # in R units

    # Deduplication key (used for cooldown tracking)
    cooldown_key: str = ""

    qualified_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal.signal_id,
            "symbol": self.signal.symbol,
            "family": self.signal.family,
            "interval": self.signal.interval,
            "direction": self.signal.direction,
            "entry_price": self.signal.entry_price,
            "stop_loss": self.signal.stop_loss,
            "take_profit": self.signal.take_profit,
            "take_profit_2": self.signal.take_profit_2,
            "confidence_score": self.signal.confidence_score,
            "risk_reward_ratio": self.signal.risk_reward_ratio,
            "position_size_pct": round(self.position_size_pct, 4),
            "position_size_usd": round(self.position_size_usd, 2),
            "risk_amount_usd": round(self.risk_amount_usd, 2),
            "market_regime": self.market_regime,
            "btc_structure": self.btc_structure,
            "session_name": self.session_name,
            "expected_value_r": round(self.expected_value_r, 4),
            "cooldown_key": self.cooldown_key,
            "qualified_at": self.qualified_at,
            "layer_results": [
                {"layer": r.layer_name, "verdict": r.verdict,
                 "reason": r.reason, **r.metadata}
                for r in self.layer_results
            ],
        }


@dataclass
class GateRejection:
    """Returned when a signal is blocked by any gate layer."""
    signal_id: str
    symbol: str
    family: str
    direction: str
    blocked_by_layer: str
    block_reason: str
    layer_results: List[LayerResult] = field(default_factory=list)
    rejected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "family": self.family,
            "direction": self.direction,
            "blocked_by_layer": self.blocked_by_layer,
            "block_reason": self.block_reason,
            "rejected_at": self.rejected_at,
        }
