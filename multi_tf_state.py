from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional


TF_MINUTES: Dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15,
    "30m": 30, "1h": 60, "2h": 120, "4h": 240,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts_to_iso(value: Any) -> str:
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return _now_iso()
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(value, datetime):
        return (value.astimezone(timezone.utc) if value.tzinfo
                else value.replace(tzinfo=timezone.utc)).isoformat()
    return _now_iso()


# ─────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────

@dataclass
class TFBar:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    n_trades: int = 0


@dataclass
class TFState:
    """State for one (symbol, timeframe) pair."""
    symbol: str
    interval: str
    bars: Deque[TFBar] = field(default_factory=lambda: deque(maxlen=500))
    indicators: Dict[str, float] = field(default_factory=dict)
    regime: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[str] = None

    def opens(self) -> List[float]:
        return [b.open for b in self.bars]

    def closes(self) -> List[float]:
        return [b.close for b in self.bars]

    def highs(self) -> List[float]:
        return [b.high for b in self.bars]

    def lows(self) -> List[float]:
        return [b.low for b in self.bars]

    def volumes(self) -> List[float]:
        return [b.volume for b in self.bars]

    def ready(self, min_bars: int = 50) -> bool:
        return len(self.bars) >= min_bars

    def append_or_replace(self, bar: TFBar) -> None:
        if self.bars and self.bars[-1].ts == bar.ts:
            self.bars[-1] = bar
        else:
            self.bars.append(bar)
        self.updated_at = _now_iso()


@dataclass
class MultiTFSymbolState:
    """All timeframe states + crypto-native context for one symbol."""
    symbol: str
    tf_states: Dict[str, TFState] = field(default_factory=dict)

    # L2 orderbook (from l2Book subscription)
    bid_levels: List[tuple] = field(default_factory=list)   # [(price, size), ...]
    ask_levels: List[tuple] = field(default_factory=list)
    book_updated_at: Optional[str] = None

    # Crypto-native context (from activeAssetCtx subscription)
    funding_rate: float = 0.0
    open_interest: float = 0.0
    mark_price: float = 0.0
    prev_day_px: float = 0.0
    ctx_updated_at: Optional[str] = None

    def get_tf(self, interval: str) -> Optional[TFState]:
        return self.tf_states.get(interval)

    def best_available_tf(self, preferred_tfs: List[str]) -> Optional[str]:
        """Return first TF from preferred_tfs that has enough bars (>=50)."""
        for tf in preferred_tfs:
            s = self.tf_states.get(tf)
            if s and s.ready(50):
                return tf
        return None

    def htf_bias(self, htf: str = "15m") -> str:
        """
        Returns 'bullish' | 'bearish' | 'neutral'.
        Logic: ADX >= 20 required. MACD + EMA spread alignment.
        Falls back to 'neutral' when insufficient data.
        """
        tf = self.get_tf(htf)
        if tf is None or not tf.ready(35):
            return "neutral"

        adx = tf.indicators.get("adx_14", 0.0)
        if adx < 20.0:
            return "neutral"   # no directional trend

        macd = tf.indicators.get("MACD", 0.0)
        macd_sig = tf.indicators.get("MACD_signal", 0.0)
        ema_spread = tf.indicators.get("ema_spread_8_21", 0.0)
        rsi = tf.indicators.get("rsi_14", 50.0)

        bull_votes = sum([
            macd > macd_sig,
            ema_spread > 0,
            rsi > 52,
        ])
        bear_votes = sum([
            macd < macd_sig,
            ema_spread < 0,
            rsi < 48,
        ])

        if bull_votes >= 2:
            return "bullish"
        if bear_votes >= 2:
            return "bearish"
        return "neutral"

    def mtf_alignment(self, tfs: List[str] = None) -> float:
        """
        Returns alignment score: -1.0 (all bearish) → 0.0 (mixed) → +1.0 (all bullish).
        Skips TFs with insufficient data — does NOT penalize missing TFs.
        """
        if tfs is None:
            tfs = ["5m", "15m", "1h"]
        scores = []
        for tf_str in tfs:
            bias = self.htf_bias(tf_str)
            if bias == "bullish":
                scores.append(1.0)
            elif bias == "bearish":
                scores.append(-1.0)
            # "neutral" → skip, not 0.0, to avoid penalizing warmup period
        return sum(scores) / len(scores) if scores else 0.0

    def funding_rate_zscore(self, window_hint: float = 0.01) -> float:
        """
        Simple zscore-like measure: funding_rate / typical_funding.
        typical_funding ≈ 0.01% per 8h = 0.0001. Returns signed magnitude.
        """
        typical = 0.0001
        return self.funding_rate / typical if typical else 0.0

    def orderbook_imbalance(self, levels: int = 5) -> float:
        """
        Bid/ask size imbalance from top N levels.
        +1.0 = pure bid pressure, -1.0 = pure ask pressure.
        """
        bid_sz = sum(sz for _, sz in self.bid_levels[:levels])
        ask_sz = sum(sz for _, sz in self.ask_levels[:levels])
        total = bid_sz + ask_sz
        return (bid_sz - ask_sz) / total if total else 0.0


# ─────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────

class MultiTFEngine:
    """
    Manages multi-timeframe bar states for all configured symbols.
    Receives candle / l2Book / activeAssetCtx messages from WS.
    Thread-safe: GIL-protected dict updates are atomic for CPython.
    """

    def __init__(self, asset_config: Dict[str, Any], max_bars_per_tf: Dict[str, int]):
        self.asset_config = asset_config
        self.max_bars_per_tf = max_bars_per_tf
        self.states: Dict[str, MultiTFSymbolState] = {}

        for symbol, cfg in asset_config.items():
            s = MultiTFSymbolState(symbol=symbol)
            for interval in cfg.get("candle_intervals", []):
                maxlen = max_bars_per_tf.get(interval, 300)
                s.tf_states[interval] = TFState(
                    symbol=symbol,
                    interval=interval,
                    bars=deque(maxlen=maxlen),
                )
            self.states[symbol] = s

    def get(self, symbol: str) -> Optional[MultiTFSymbolState]:
        return self.states.get(symbol)

    def handle_candle(self, data: Dict[str, Any]) -> None:
        """Route incoming candle WS message to the correct TFState."""
        candle = data.get("candle", data)
        if not isinstance(candle, dict):
            return

        symbol = candle.get("s") or candle.get("coin") or candle.get("symbol")
        interval = candle.get("i") or candle.get("interval") or "1m"
        state = self.states.get(symbol)
        if not state or not interval:
            return
        tf_state = state.tf_states.get(interval)
        if tf_state is None:
            return

        bar = TFBar(
            ts=_ts_to_iso(candle.get("t") or candle.get("T")),
            open=float(candle.get("o", candle.get("open", 0.0))),
            high=float(candle.get("h", candle.get("high", 0.0))),
            low=float(candle.get("l", candle.get("low", 0.0))),
            close=float(candle.get("c", candle.get("close", 0.0))),
            volume=float(candle.get("v", candle.get("volume", 0.0))),
            n_trades=int(candle.get("n", 0)),
        )
        tf_state.append_or_replace(bar)

    def handle_l2book(self, data: Dict[str, Any]) -> None:
        """Update L2 orderbook state for a symbol."""
        symbol = data.get("coin") or data.get("s")
        state = self.states.get(symbol)
        if not state:
            return
        levels = data.get("levels", [[], []])
        bids_raw = levels[0] if len(levels) > 0 else []
        asks_raw = levels[1] if len(levels) > 1 else []
        try:
            state.bid_levels = [
                (float(lv["px"]), float(lv["sz"])) for lv in bids_raw[:20]
            ]
            state.ask_levels = [
                (float(lv["px"]), float(lv["sz"])) for lv in asks_raw[:20]
            ]
        except (KeyError, TypeError, ValueError):
            pass
        state.book_updated_at = _now_iso()

    def handle_active_asset_ctx(self, data: Dict[str, Any]) -> None:
        """Update funding rate + OI from activeAssetCtx message."""
        symbol = data.get("coin")
        ctx = data.get("ctx", {})
        state = self.states.get(symbol)
        if not state or not isinstance(ctx, dict):
            return
        try:
            state.funding_rate = float(ctx.get("funding", 0.0))
            state.open_interest = float(ctx.get("openInterest", 0.0))
            state.mark_price = float(ctx.get("markPx", 0.0))
            state.prev_day_px = float(ctx.get("prevDayPx", 0.0))
        except (TypeError, ValueError):
            pass
        state.ctx_updated_at = _now_iso()

    def symbols(self) -> List[str]:
        return list(self.states.keys())

    def get_asset_role(self, symbol: str) -> str:
        return self.asset_config.get(symbol, {}).get("role", "major")
