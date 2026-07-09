from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Union

from multi_tf_state import MultiTFEngine
from quality_gate_models import (
    BLOCK_REASON_COOLDOWN, BLOCK_REASON_DISABLED,
    BLOCK_REASON_PORTFOLIO, BLOCK_REASON_REGIME,
    BLOCK_REASON_SESSION, BLOCK_REASON_STATISTICAL,
    GATE_BLOCK, GATE_PASS,
    GateRejection, LayerResult, QualifiedSignal, QualityGateConfig,
)
from signal_models import DIRECTION_LONG, DIRECTION_SHORT, SignalResult

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hour_in_window(hour: int, start: int, end: int) -> bool:
    """Check if hour is in [start, end) window, handles midnight wrap."""
    if start <= end:
        return start <= hour < end
    else:                        # wrap: e.g. (22, 2) = 22,23,0,1
        return hour >= start or hour < end


def _classify_session(hour: int) -> str:
    """Return named session for logging purposes."""
    if 13 <= hour < 17:
        return "ny_london_overlap"
    if 13 <= hour < 22:
        return "new_york"
    if 7 <= hour < 16:
        return "london"
    if 1 <= hour < 9:
        return "asia"
    return "off_hours"


def _calc_kelly_fraction(win_rate: float, rr_ratio: float) -> float:
    """
    Full Kelly fraction = (win_rate * rr_ratio - loss_rate) / rr_ratio
    where loss_rate = 1 - win_rate.
    Returns 0.0 if result is negative (no edge).
    """
    if rr_ratio <= 0:
        return 0.0
    loss_rate = 1.0 - win_rate
    kelly = (win_rate * rr_ratio - loss_rate) / rr_ratio
    return max(0.0, kelly)


def _calc_ev(win_rate: float, rr_ratio: float) -> float:
    """
    Expected value in R units.
    EV = win_rate * rr_ratio - (1 - win_rate) * 1.0
    """
    return win_rate * rr_ratio - (1.0 - win_rate)


def _confidence_to_size_scale(confidence: float,
                               size_map: Dict[str, float]) -> float:
    """
    Map confidence score to size scale factor using step lookup.
    Returns scale factor 0.0–1.0.
    """
    thresholds = sorted(float(k) for k in size_map.keys())
    scale = 0.0
    for thresh in thresholds:
        if confidence >= thresh:
            scale = size_map[f"{thresh:.2f}"]
    return scale


# ─────────────────────────────────────────────────────────────────────
# Layer 1 — Session filter
# ─────────────────────────────────────────────────────────────────────

def _layer_session(signal: SignalResult,
                   cfg: QualityGateConfig) -> LayerResult:
    """
    Block signals during dead zones or outside all active sessions.
    """
    if not cfg.session.enabled:
        return LayerResult("session", GATE_PASS, "session_filter_disabled")

    now = _utc_now()
    hour = now.hour
    minute = now.minute

    # Dead zone check (hard block)
    for (dz_start, dz_end) in cfg.session.dead_zones:
        if _hour_in_window(hour, dz_start, dz_end):
            return LayerResult(
                "session", GATE_BLOCK, BLOCK_REASON_SESSION,
                {"dead_zone": f"{dz_start:02d}:00-{dz_end:02d}:00 UTC",
                 "current_hour_utc": hour},
            )

    # Active session check
    in_any_session = False
    for (s_start, s_end) in cfg.session.sessions:
        if _hour_in_window(hour, s_start, s_end):
            if s_start < s_end:
                mins_remaining = s_end * 60 - (hour * 60 + minute)
            else:
                if hour >= s_start:
                    mins_remaining = (s_end + 24) * 60 - (hour * 60 + minute)
                else:
                    mins_remaining = s_end * 60 - (hour * 60 + minute)
            
            if mins_remaining < cfg.session.block_near_session_end_minutes:
                continue   # skip this session (too close to end)
            in_any_session = True
            break

    session_name = _classify_session(hour)

    if not in_any_session:
        return LayerResult(
            "session", GATE_BLOCK, BLOCK_REASON_SESSION,
            {"reason": "outside_all_active_sessions",
             "current_hour_utc": hour,
             "session_name": session_name},
        )

    return LayerResult(
        "session", GATE_PASS, "",
        {"session_name": session_name, "current_hour_utc": hour},
    )


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — Market regime filter
# ─────────────────────────────────────────────────────────────────────

def _layer_regime(signal: SignalResult,
                  mtf_engine: MultiTFEngine,
                  cfg: QualityGateConfig) -> LayerResult:
    """
    Classify market regime from anchor asset (BTC) on reference TF.
    Block signals whose family is incompatible with current regime.
    Also apply BTC structure bias (no new longs in BTC bear structure).
    """
    if not cfg.regime.enabled:
        return LayerResult("regime", GATE_PASS, "regime_filter_disabled")

    anchor = cfg.regime.anchor_symbol
    ref_tf = cfg.regime.reference_interval
    sym_state = mtf_engine.get(anchor)

    if sym_state is None:
        return LayerResult("regime", GATE_PASS, "anchor_not_found_skip",
                           {"anchor": anchor})

    tf_state = sym_state.get_tf(ref_tf)
    if tf_state is None or not tf_state.bars:
        return LayerResult("regime", GATE_PASS, "anchor_tf_no_bars_skip")

    ind = tf_state.indicators
    adx = ind.get("adx_14", 0.0)
    ema_spread = ind.get("ema_spread_8_21", 0.0)
    rsi = ind.get("rsi_14", 50.0)

    # Classify regime
    if adx >= cfg.regime.adx_trending_min:
        regime = "trending"
    elif adx <= cfg.regime.adx_choppy_max:
        regime = "choppy"
    else:
        regime = "transitional"

    # BTC structure bias
    if ema_spread > cfg.regime.btc_bull_ema_threshold:
        btc_structure = "bullish"
    elif ema_spread < cfg.regime.btc_bear_ema_threshold:
        btc_structure = "bearish"
    else:
        btc_structure = "neutral"

    # Check family regime compatibility
    family = signal.family
    allowed_regime = cfg.regime.family_regime_map.get(family, "any")

    if allowed_regime == "trend_only" and regime == "choppy":
        return LayerResult(
            "regime", GATE_BLOCK, BLOCK_REASON_REGIME,
            {"reason": f"{family}_requires_trending_regime",
             "current_regime": regime, "adx": adx,
             "btc_structure": btc_structure},
        )

    if allowed_regime == "range_only" and regime == "trending":
        return LayerResult(
            "regime", GATE_BLOCK, BLOCK_REASON_REGIME,
            {"reason": f"{family}_requires_ranging_regime",
             "current_regime": regime, "adx": adx,
             "btc_structure": btc_structure},
        )

    # BTC bear structure → block new longs on all correlated assets
    if (cfg.regime.enable_btc_structure_bias and
            btc_structure == "bearish" and
            signal.direction == DIRECTION_LONG and
            signal.family not in ("funding_reversion", "oi_reversal")):
        return LayerResult(
            "regime", GATE_BLOCK, BLOCK_REASON_REGIME,
            {"reason": "btc_bear_structure_blocks_longs",
             "btc_ema_spread": ema_spread,
             "btc_structure": btc_structure},
        )

    # BTC bull structure → block new shorts (optional, softer rule)
    # Uncomment if desired:
    # if btc_structure == "bullish" and signal.direction == DIRECTION_SHORT:
    #     return LayerResult("regime", GATE_BLOCK, ...)

    return LayerResult(
        "regime", GATE_PASS, "",
        {"regime": regime, "adx": adx,
         "btc_structure": btc_structure,
         "ema_spread": ema_spread},
    )


# ─────────────────────────────────────────────────────────────────────
# Layer 3 — Portfolio / correlation / cooldown filter
# ─────────────────────────────────────────────────────────────────────

def _layer_portfolio(signal: SignalResult,
                     active_signals: List[str],
                     active_clusters: Dict[str, int],
                     cooldown_registry: Dict[str, float],
                     portfolio_heat: float,
                     cfg: QualityGateConfig) -> LayerResult:
    """
    Check portfolio-level constraints:
    1. Max concurrent signals
    2. Max per correlation cluster
    3. Cooldown per (symbol, family, direction)
    4. Portfolio heat cap
    """
    if not cfg.portfolio.enabled:
        return LayerResult("portfolio", GATE_PASS, "portfolio_filter_disabled")

    pcfg = cfg.portfolio

    # 1. Cooldown check
    cooldown_key = f"{signal.symbol}_{signal.family}_{signal.direction}"
    last_fire = cooldown_registry.get(cooldown_key, 0.0)
    now_ts = time.time()
    elapsed = now_ts - last_fire
    if elapsed < pcfg.cooldown_seconds:
        remaining = pcfg.cooldown_seconds - elapsed
        return LayerResult(
            "portfolio", GATE_BLOCK, BLOCK_REASON_COOLDOWN,
            {"cooldown_key": cooldown_key,
             "cooldown_remaining_seconds": round(remaining, 1),
             "cooldown_total_seconds": pcfg.cooldown_seconds},
        )

    # 2. Max concurrent signals
    current_count = len(active_signals)
    if current_count >= pcfg.max_concurrent_signals:
        return LayerResult(
            "portfolio", GATE_BLOCK, BLOCK_REASON_PORTFOLIO,
            {"reason": "max_concurrent_signals_reached",
             "current": current_count,
             "max": pcfg.max_concurrent_signals},
        )

    # 3. Correlation cluster check
    cluster_id = pcfg.correlation_clusters.get(signal.symbol, signal.symbol)
    cluster_count = active_clusters.get(cluster_id, 0)
    if cluster_count >= pcfg.max_signals_per_cluster:
        return LayerResult(
            "portfolio", GATE_BLOCK, BLOCK_REASON_PORTFOLIO,
            {"reason": "max_cluster_signals_reached",
             "cluster": cluster_id,
             "current": cluster_count,
             "max": pcfg.max_signals_per_cluster},
        )

    # 4. Portfolio heat check
    if portfolio_heat >= pcfg.max_portfolio_heat_pct:
        return LayerResult(
            "portfolio", GATE_BLOCK, BLOCK_REASON_PORTFOLIO,
            {"reason": "max_portfolio_heat_reached",
             "current_heat_pct": round(portfolio_heat, 2),
             "max_heat_pct": pcfg.max_portfolio_heat_pct},
        )

    return LayerResult(
        "portfolio", GATE_PASS, "",
        {"cooldown_key": cooldown_key,
         "cluster": cluster_id,
         "cluster_count": cluster_count,
         "portfolio_heat_pct": round(portfolio_heat, 2),
         "concurrent_count": current_count},
    )


# ─────────────────────────────────────────────────────────────────────
# Layer 4 — Statistical validity / EV gate
# ─────────────────────────────────────────────────────────────────────

def _layer_statistical(signal: SignalResult,
                        cfg: QualityGateConfig) -> Tuple[LayerResult, float]:
    """
    Check minimum confidence, minimum RR, and positive expected value.
    Returns (LayerResult, ev_r) — ev_r used for position sizing.
    """
    if not cfg.statistical.enabled:
        return (LayerResult("statistical", GATE_PASS,
                            "statistical_filter_disabled"), 0.0)

    scfg = cfg.statistical

    # Minimum confidence
    if signal.confidence_score < scfg.min_confidence:
        return (LayerResult(
            "statistical", GATE_BLOCK, BLOCK_REASON_STATISTICAL,
            {"reason": "confidence_below_minimum",
             "confidence": signal.confidence_score,
             "min_confidence": scfg.min_confidence},
        ), 0.0)

    # Minimum RR
    if signal.risk_reward_ratio < scfg.min_rr_ratio:
        return (LayerResult(
            "statistical", GATE_BLOCK, BLOCK_REASON_STATISTICAL,
            {"reason": "rr_below_minimum",
             "rr": signal.risk_reward_ratio,
             "min_rr": scfg.min_rr_ratio},
        ), 0.0)

    # EV check
    # Map specific upgraded families to generic parent families for win rate lookup
    parent_family = signal.family
    if parent_family in ("macd_trend_continuation", "ema_pullback_buy", "bearish_trend_continuation", "ema_pullback_sell"):
        parent_family = "continuation"
    elif parent_family in ("obv_accumulation_breakout", "high_vol_breakout", "momentum_chasing", "high_vol_breakdown", "short_momentum_chase", "obv_distribution_breakdown", "breakout"):
        parent_family = "breakout"
    elif parent_family in ("vwap_reversion_fade", "range_boundary_fade", "liquidity_sweep_hunt", "oversold_bounce", "mean_reversion_squeeze", "mean_reversion"):
        parent_family = "mean_reversion"
    elif parent_family in ("hft_order_flow_momentum", "order_flow"):
        parent_family = "order_flow"

    win_rate = scfg.family_win_rates.get(parent_family, 0.50)
    # Adjust win_rate slightly based on confidence
    confidence_bonus = (signal.confidence_score - 0.50) * 0.1
    adjusted_win_rate = min(0.80, win_rate + confidence_bonus)
    
    ev = _calc_ev(adjusted_win_rate, signal.risk_reward_ratio)

    if ev < scfg.min_ev_r:
        return (LayerResult(
            "statistical", GATE_BLOCK, BLOCK_REASON_STATISTICAL,
            {"reason": "ev_below_minimum",
             "ev_r": round(ev, 4),
             "min_ev_r": scfg.min_ev_r,
             "win_rate": adjusted_win_rate,
             "rr": signal.risk_reward_ratio},
        ), ev)

    return (LayerResult(
        "statistical", GATE_PASS, "",
        {"ev_r": round(ev, 4),
         "win_rate": adjusted_win_rate,
         "rr": signal.risk_reward_ratio,
         "confidence": signal.confidence_score},
    ), ev)


# ─────────────────────────────────────────────────────────────────────
# Layer 5 — Position sizing
# ─────────────────────────────────────────────────────────────────────

def _layer_sizing(signal: SignalResult,
                  ev_r: float,
                  cfg: QualityGateConfig) -> Tuple[LayerResult, float, float, float]:
    """
    Compute position size using half-Kelly fraction, capped by config.
    Returns (LayerResult, position_size_pct, position_size_usd, risk_usd).
    """
    if not cfg.sizing.enabled:
        fallback_pct = cfg.sizing.min_position_pct
        fallback_usd = cfg.sizing.account_equity * fallback_pct / 100
        return (LayerResult("sizing", GATE_PASS, "sizing_disabled"),
                fallback_pct, fallback_usd, 0.0)

    scfg = cfg.sizing
    stat = cfg.statistical

    win_rate = stat.family_win_rates.get(signal.family, 0.50)
    rr = signal.risk_reward_ratio

    # Kelly fraction
    full_kelly = _calc_kelly_fraction(win_rate, rr)
    half_kelly = full_kelly * scfg.kelly_fraction   # half-Kelly for safety

    # Convert to % of account
    base_pct = half_kelly * 100.0

    # Scale by confidence
    conf_scale = _confidence_to_size_scale(
        signal.confidence_score,
        scfg.confidence_to_size_map,
    )

    # Scale by asset role
    role_scale = scfg.role_size_multiplier.get(signal.asset_role, 0.75)

    # Final size
    final_pct = base_pct * conf_scale * role_scale

    # Clamp to [min, max]
    final_pct = max(scfg.min_position_pct, min(scfg.max_position_pct, final_pct))

    # USD size
    final_usd = scfg.account_equity * final_pct / 100.0

    # Risk amount: size * (SL distance as % of entry)
    if signal.entry_price > 0 and signal.stop_loss > 0:
        sl_dist_pct = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        risk_usd = final_usd * sl_dist_pct
    else:
        risk_usd = 0.0

    return (LayerResult(
        "sizing", GATE_PASS, "",
        {"position_size_pct": round(final_pct, 4),
         "position_size_usd": round(final_usd, 2),
         "risk_usd": round(risk_usd, 2),
         "full_kelly": round(full_kelly, 4),
         "half_kelly": round(half_kelly, 4),
         "conf_scale": conf_scale,
         "role_scale": role_scale,
         "win_rate_used": win_rate},
    ), final_pct, final_usd, risk_usd)


# ─────────────────────────────────────────────────────────────────────
# Main QualityGate class
# ─────────────────────────────────────────────────────────────────────

class QualityGate:
    """
    5-layer quality gate pipeline for signal validation and sizing.

    Usage:
        gate = QualityGate(config, mtf_engine)
        result = gate.evaluate(signal)
        if isinstance(result, QualifiedSignal):
            # Signal passed all gates — use result.position_size_usd
            pass
        else:
            # Signal rejected — result is GateRejection
            pass
    """

    def __init__(self, config: QualityGateConfig, mtf_engine: MultiTFEngine):
        self._cfg = config
        self._mtf = mtf_engine

        # Cooldown registry: cooldown_key → last_fire_timestamp (epoch seconds)
        self._cooldown: Dict[str, float] = {}

        # Active signal tracking: signal_id → (symbol, cluster_id)
        self._active_signals: Dict[str, Tuple[str, str]] = {}

        # Portfolio heat: total % at risk
        self._portfolio_heat: float = 0.0

        # Rejection log — giữ tối đa 100 rejections gần nhất
        self.rejection_log: deque = deque(maxlen=100)

        # Cache regime state cuối cùng (để dashboard đọc nhanh)
        self._last_regime: str = "unknown"
        self._last_btc_structure: str = "neutral"
        self._last_session: str = "unknown"

    # ── Public API ────────────────────────────────────────────────────

    def evaluate(
        self,
        signal: SignalResult,
    ) -> Union[QualifiedSignal, GateRejection]:
        """
        Run signal through all 5 layers in sequence.
        Returns QualifiedSignal if all pass, GateRejection if any block.
        """
        if not self._cfg.enabled:
            return GateRejection(
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                family=signal.family,
                direction=signal.direction,
                blocked_by_layer="global",
                block_reason=BLOCK_REASON_DISABLED,
            )

        # Check system_config adaptive_rr
        from globals import CONFIG
        system_config = CONFIG.get('system_config', {})
        if system_config.get('adaptive_rr', False):
            sym_state = self._mtf.get(signal.symbol)
            if sym_state:
                interval = getattr(signal, 'interval', '1m')
                tf_state = sym_state.get_tf(interval)
                if tf_state and tf_state.indicators:
                    adx = tf_state.indicators.get("adx_14", 0.0)
                    bb_zscore = tf_state.indicators.get("BollingerWidth_ZScore", 0.0)
                    if adx > 0 and signal.stop_loss and signal.stop_loss > 0:
                        sl_dist = abs(signal.entry_price - signal.stop_loss)
                        mult = 1.3 if bb_zscore > 1.5 else 1.0
                        if bb_zscore > 1.5:
                            log.info(f"[VOLATILITY_EXPANSION] bb_zscore={bb_zscore:.2f} applying 1.3x multiplier to TP distance")
                        
                        if adx > 30:  # Strong Trend: 3.0R
                            if signal.direction == 'long':
                                signal.take_profit = signal.entry_price + (3.0 * mult * sl_dist)
                            else:
                                signal.take_profit = signal.entry_price - (3.0 * mult * sl_dist)
                            log.info(f"[ADAPTIVE_RR] Strong Trend (ADX={adx:.1f}) scaled TP to {3.0*mult:.2f}R ({signal.take_profit:.4f}) for {signal.symbol}")
                        elif adx < 18:  # Choppy Range: 1.2R
                            if signal.direction == 'long':
                                signal.take_profit = signal.entry_price + (1.2 * mult * sl_dist)
                            else:
                                signal.take_profit = signal.entry_price - (1.2 * mult * sl_dist)
                            log.info(f"[ADAPTIVE_RR] Choppy Range (ADX={adx:.1f}) scaled TP to {1.2*mult:.2f}R ({signal.take_profit:.4f}) for {signal.symbol}")

        layer_results: List[LayerResult] = []

        # ── Layer 1: Session ──────────────────────────────────────
        l1 = _layer_session(signal, self._cfg)
        layer_results.append(l1)
        if l1.verdict == GATE_BLOCK:
            return self._reject(signal, l1, layer_results)
        self._last_session = l1.metadata.get("session_name", "unknown")

        # ── Layer 1.5: Multi-Timeframe Confluence ──────────────────
        sym_state = self._mtf.get(signal.symbol)
        if sym_state:
            tf_1h = sym_state.get_tf("1h")
            if tf_1h and tf_1h.indicators:
                close_1h = getattr(tf_1h, 'last_close', getattr(tf_1h, 'close', signal.entry_price))
                ema_1h = tf_1h.indicators.get("EMA_20") or tf_1h.indicators.get("BBANDS_mid") or close_1h
                
                is_continuation = signal.family in ["macd_trend_continuation", "ema_pullback_buy", "ema_pullback_sell", "momentum_chasing"]
                if is_continuation:
                    if signal.direction == 'long' and close_1h < ema_1h:
                        l15 = LayerResult(
                            layer_name="mtf_confluence",
                            verdict=GATE_BLOCK,
                            reason=f"Blocked by MTF: Long trend continuation signal fired while 1h close ({close_1h:.2f}) is below 1h EMA_20 ({ema_1h:.2f})"
                        )
                        layer_results.append(l15)
                        return self._reject(signal, l15, layer_results)
                    elif signal.direction == 'short' and close_1h > ema_1h:
                        l15 = LayerResult(
                            layer_name="mtf_confluence",
                            verdict=GATE_BLOCK,
                            reason=f"Blocked by MTF: Short trend continuation signal fired while 1h close ({close_1h:.2f}) is above 1h EMA_20 ({ema_1h:.2f})"
                        )
                        layer_results.append(l15)
                        return self._reject(signal, l15, layer_results)
        
        l15_pass = LayerResult(layer_name="mtf_confluence", verdict=GATE_PASS)
        layer_results.append(l15_pass)

        # ── Layer 2: Regime ───────────────────────────────────────
        l2 = _layer_regime(signal, self._mtf, self._cfg)
        layer_results.append(l2)
        if l2.verdict == GATE_BLOCK:
            return self._reject(signal, l2, layer_results)
        self._last_regime       = l2.metadata.get("regime", "unknown")
        self._last_btc_structure= l2.metadata.get("btc_structure", "neutral")

        # ── Layer 3: Portfolio ────────────────────────────────────
        active_signal_ids = list(self._active_signals.keys())
        active_clusters: Dict[str, int] = defaultdict(int)
        for _, (sym, cluster) in self._active_signals.items():
            active_clusters[cluster] += 1

        l3 = _layer_portfolio(
            signal,
            active_signal_ids,
            active_clusters,
            self._cooldown,
            self._portfolio_heat,
            self._cfg,
        )
        layer_results.append(l3)
        if l3.verdict == GATE_BLOCK:
            return self._reject(signal, l3, layer_results)

        # ── Layer 4: Statistical ──────────────────────────────────
        l4, ev_r = _layer_statistical(signal, self._cfg)
        layer_results.append(l4)
        if l4.verdict == GATE_BLOCK:
            return self._reject(signal, l4, layer_results)

        # ── Layer 5: Sizing ───────────────────────────────────────
        l5, pos_pct, pos_usd, risk_usd = _layer_sizing(
            signal, ev_r, self._cfg)
        layer_results.append(l5)
        # Sizing never blocks — it always computes a valid (clamped) size

        # ── All layers passed: build QualifiedSignal ──────────────
        regime_meta = l2.metadata
        session_meta = l1.metadata
        cooldown_key = f"{signal.symbol}_{signal.family}_{signal.direction}"

        qs = QualifiedSignal(
            signal=signal,
            verdict=GATE_PASS,
            layer_results=layer_results,
            position_size_pct=pos_pct,
            position_size_usd=pos_usd,
            risk_amount_usd=risk_usd,
            market_regime=regime_meta.get("regime", "unknown"),
            btc_structure=regime_meta.get("btc_structure", "neutral"),
            session_name=session_meta.get("session_name", "unknown"),
            expected_value_r=ev_r,
            cooldown_key=cooldown_key,
        )
        
        # Generate Dynamic Trade Thesis
        thesis_parts = []
        thesis_parts.append(f"Execute {signal.direction.upper()} on {signal.symbol} ({signal.interval}) at entry ${signal.entry_price:.2f}.")
        thesis_parts.append(f"Regime: {qs.market_regime.upper()} ({qs.btc_structure.upper()} BTC structure) during {qs.session_name.upper()} session.")
        
        sym_state = self._mtf.get(signal.symbol)
        if sym_state:
            tf_state = sym_state.get_tf(signal.interval)
            if tf_state and tf_state.indicators:
                inds = tf_state.indicators
                rsi = inds.get("rsi_14") or inds.get("RSI_HMA_14") or 50.0
                adx = inds.get("adx_14") or 20.0
                obi = inds.get("book_imbalance_5") or 0.0
                cvd = inds.get("cvd_slope_20") or 0.0
                bb_z = inds.get("BollingerWidth_ZScore") or 0.0
                
                thesis_parts.append(f"Microstructure context:")
                thesis_parts.append(f"- Trend Strength: ADX={adx:.1f}")
                thesis_parts.append(f"- Momentum: RSI={rsi:.1f}")
                thesis_parts.append(f"- Order Book Imbalance: D-OBI={obi*100.0:+.1f}%")
                if abs(cvd) > 0.0:
                    thesis_parts.append(f"- CVD Slope: {cvd:.4f}")
                if bb_z > 1.5:
                    thesis_parts.append(f"- Volatility Expansion: Bollinger Z-Score={bb_z:.2f} (Target scaled by 1.3x)")
                elif bb_z < -1.5:
                    thesis_parts.append(f"- Volatility Squeeze: Bollinger Z-Score={bb_z:.2f}")
                    
        qs.thesis = " ".join(thesis_parts)

        # Register in state tracking
        self._register_signal(signal, cooldown_key, risk_usd, pos_pct)

        log.info(
            f"[GATE_PASS] {signal.symbol} {signal.family.upper()} "
            f"{signal.direction.upper()} | "
            f"size={pos_pct:.2f}% (${pos_usd:.0f}) | "
            f"risk=${risk_usd:.0f} | EV={ev_r:.3f}R | "
            f"regime={qs.market_regime} | session={qs.session_name}"
        )

        return qs

    def on_signal_closed(self, signal_id: str) -> None:
        """
        Call this when a trade is closed (paper_broker callback).
        Removes signal from active tracking and reduces portfolio heat.
        """
        if signal_id in self._active_signals:
            _, _ = self._active_signals.pop(signal_id)
            log.debug(f"[GATE] signal_closed {signal_id}")

    def update_portfolio_heat(self, heat_pct: float) -> None:
        """Update total portfolio heat from external source (paper_broker)."""
        self._portfolio_heat = heat_pct

    def update_account_equity(self, equity_usd: float) -> None:
        """Update account equity for position sizing."""
        self._cfg.sizing.account_equity = equity_usd

    @property
    def gate_summary(self) -> dict:
        """Snapshot nhanh để dashboard đọc — không lock, không tính lại."""
        return {
            "active_signal_count":   self.active_signal_count,
            "portfolio_heat_pct":    round(self._portfolio_heat, 2),
            "account_equity_usd":    self._cfg.sizing.account_equity,
            "market_regime":         self._last_regime,
            "btc_structure":         self._last_btc_structure,
            "session_name":          self._last_session,
            "max_concurrent":        self._cfg.portfolio.max_concurrent_signals,
            "max_heat_pct":          self._cfg.portfolio.max_portfolio_heat_pct,
            "gate_enabled":          self._cfg.enabled,
            "cooldown_count":        len(self._cooldown),
        }

    @property
    def active_signal_count(self) -> int:
        return len(self._active_signals)

    @property
    def portfolio_heat(self) -> float:
        return self._portfolio_heat

    # ── Private helpers ───────────────────────────────────────────────

    def _reject(self, signal: SignalResult,
                blocking_layer: LayerResult,
                all_layers: List[LayerResult]) -> GateRejection:
        rejection = GateRejection(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            family=signal.family,
            direction=signal.direction,
            blocked_by_layer=blocking_layer.layer_name,
            block_reason=blocking_layer.reason,
            layer_results=all_layers,
        )
        self.rejection_log.append(rejection)
        log.debug(
            f"[GATE_BLOCK] {signal.symbol} {signal.family} "
            f"{signal.direction} | layer={blocking_layer.layer_name} | "
            f"reason={blocking_layer.reason}"
        )
        return rejection

    def _register_signal(self, signal: SignalResult,
                         cooldown_key: str,
                         risk_usd: float,
                         pos_pct: float) -> None:
        """Register a passing signal in internal state."""
        # Update cooldown
        self._cooldown[cooldown_key] = time.time()

        # Add to active signals
        cluster_id = self._cfg.portfolio.correlation_clusters.get(
            signal.symbol, signal.symbol
        )
        self._active_signals[signal.signal_id] = (signal.symbol, cluster_id)

        # Update heat: approximate as pos_pct contribution
        # More accurate: risk_usd / account_equity * 100
        equity = self._cfg.sizing.account_equity
        if equity > 0:
            heat_contribution = risk_usd / equity * 100
            self._portfolio_heat = min(
                self._cfg.portfolio.max_portfolio_heat_pct,
                self._portfolio_heat + heat_contribution,
            )
