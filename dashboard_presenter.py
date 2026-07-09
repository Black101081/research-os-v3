from __future__ import annotations

import globals
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────
# Helper: safe read quality_gate
# ─────────────────────────────────────────────────────────────────────

def _gate():
    """Return globals.quality_gate or None. Never raises."""
    return getattr(globals, "quality_gate", None)


def _gate_summary() -> Dict[str, Any]:
    """Safe wrapper around QualityGate.gate_summary."""
    gate = _gate()
    if gate is None:
        return {
            "active_signal_count":   0,
            "portfolio_heat_pct":    0.0,
            "account_equity_usd":    0.0,
            "market_regime":         "unknown",
            "btc_structure":         "neutral",
            "session_name":          "unknown",
            "max_concurrent":        4,
            "max_heat_pct":          6.0,
            "gate_enabled":          False,
            "cooldown_count":        0,
        }
    try:
        return gate.gate_summary
    except Exception:
        return {
            "active_signal_count":   0,
            "portfolio_heat_pct":    0.0,
            "account_equity_usd":    0.0,
            "market_regime":         "unknown",
            "btc_structure":         "neutral",
            "session_name":          "unknown",
            "max_concurrent":        4,
            "max_heat_pct":          6.0,
            "gate_enabled":          False,
            "cooldown_count":        0,
        }   # fallback default


# ─────────────────────────────────────────────────────────────────────
# get_overview_payload  (SỬA — thêm gate fields)
# ─────────────────────────────────────────────────────────────────────

def get_overview_payload() -> Dict[str, Any]:
    snap = globals.engine.snapshot()
    summary = globals.broker.get_summary()
    telemetry_metrics = globals.telemetry.get_metrics()
    gate_sum = _gate_summary()

    # ── Legacy signal counts (giữ để backward compat) ──
    active_sig_count = 0
    confirmed_sig_count = 0
    execution_ready_count = 0

    for symbol, state in snap.items():
        for signal_payload in state.get("signals", {}).values():
            if signal_payload.get("active"):
                active_sig_count += 1
            if signal_payload.get("confirmed"):
                confirmed_sig_count += 1
        for strat_payload in state.get("strategies", {}).values():
            if strat_payload.get("execution_ready"):
                execution_ready_count += 1

    overview = {
        # ── Fields cũ (giữ nguyên) ──
        "mode":                    globals.trading_mode,
        "kill_switch_active":      globals.kill_switch_active,
        "latency_ms":              round(telemetry_metrics.get("avg_latency_ms", 0.0), 2),
        "error_rate":              round(telemetry_metrics.get("error_rate_pct", 0.0), 2),
        "uptime_seconds":          telemetry_metrics.get("uptime_seconds", 0),
        "active_signal_count":     active_sig_count,
        "confirmed_signal_count":  confirmed_sig_count,
        "execution_ready_count":   execution_ready_count,
        "open_positions_count":    summary.get("active_positions_count", 0),
        "symbols":                 globals.CONFIG["symbols"],
        "candle_interval":         globals.CONFIG["candle_interval"],

        # ── Fields MỚI từ Quality Gate ──
        "quality_gate": {
            "enabled":              gate_sum["gate_enabled"],
            "active_signals":       gate_sum["active_signal_count"],
            "portfolio_heat_pct":   gate_sum["portfolio_heat_pct"],
            "max_heat_pct":         gate_sum["max_heat_pct"],
            "heat_utilization_pct": round(
                gate_sum["portfolio_heat_pct"] / gate_sum["max_heat_pct"] * 100
                if gate_sum["max_heat_pct"] > 0 else 0.0, 1
            ),
            "account_equity_usd":   gate_sum["account_equity_usd"],
            "market_regime":        gate_sum["market_regime"],
            "btc_structure":        gate_sum["btc_structure"],
            "session_name":         gate_sum["session_name"],
            "max_concurrent":       gate_sum["max_concurrent"],
            "cooldown_active_count": gate_sum["cooldown_count"],
        },
    }

    # ── Symbols list (giữ nguyên logic cũ) ──
    symbols_list = []
    for symbol in globals.CONFIG["symbols"]:
        state = snap.get(symbol, {})
        if not state:
            continue

        regime_state = state.get("regime_state", {})
        signals = state.get("signals", {})

        triggered_cnt = confirmed_cnt = active_cnt = invalidated_cnt = 0
        top_signals = []

        for name, sig in signals.items():
            if sig.get("triggered"):
                triggered_cnt += 1
            if sig.get("confirmed"):
                confirmed_cnt += 1
            if sig.get("active"):
                active_cnt += 1
                top_signals.append(name)
            if sig.get("invalidated"):
                invalidated_cnt += 1

        symbols_list.append({
            "symbol":            symbol,
            "last_trade":        state.get("last_trade") or state.get("mid"),
            "mid":               state.get("mid"),
            "updated_at":        state.get("updated_at"),
            "regime":            regime_state.get("regime"),
            "regime_confidence": regime_state.get("confidence", 0.0),
            "tradable":          regime_state.get("tradable", False),
            "bars_loaded":       len(state.get("bars", [])),
            "signal_summary": {
                "total":       len(signals),
                "triggered":   triggered_cnt,
                "confirmed":   confirmed_cnt,
                "active":      active_cnt,
                "invalidated": invalidated_cnt,
            },
            "top_signals": top_signals,
        })

    # ── Positions (thêm Quality Gate fields) ──
    formatted_positions = []
    for pos in summary.get("positions", []):
        formatted_positions.append({
            # Fields cũ
            "symbol":         pos.get("symbol"),
            "signal_source":  pos.get("signal_source", "unknown"),
            "direction":      pos.get("direction"),
            "quantity":       pos.get("quantity"),
            "entry_price":    pos.get("entry_price"),
            "current_price":  pos.get("current_price"),
            "unrealized_pnl": pos.get("unrealized_pnl", 0.0),
            "stop_loss":      pos.get("stop_loss"),
            "take_profit":    pos.get("take_profit"),
            "entry_time":     pos.get("entry_time"),
            "status":         "OPEN",
            # Fields MỚI
            "position_size_pct":  pos.get("position_size_pct", 0.0),
            "position_size_usd":  pos.get("position_size_usd", 0.0),
            "risk_amount_usd":    pos.get("risk_amount_usd", 0.0),
            "expected_value_r":   pos.get("expected_value_r", 0.0),
            "market_regime":      pos.get("market_regime", "unknown"),
            "btc_structure":      pos.get("btc_structure", "neutral"),
            "session_at_entry":   pos.get("session_name", "unknown"),
            "confidence_score":   pos.get("confidence_score", 0.0),
            "risk_reward_ratio":  pos.get("risk_reward_ratio", 0.0),
            "family":             pos.get("family", "unknown"),
            "interval":           pos.get("interval", "unknown"),
        })

    formatted_history = []
    for trade in summary.get("trade_history", []):
        formatted_history.append({
            # Fields cũ
            "symbol":        trade.get("symbol"),
            "signal_source": trade.get("signal_source", "unknown"),
            "direction":     trade.get("direction"),
            "quantity":      trade.get("quantity"),
            "entry_price":   trade.get("entry_price"),
            "exit_price":    trade.get("exit_price"),
            "pnl":           trade.get("pnl", 0.0),
            "entry_time":    trade.get("entry_time"),
            "exit_time":     trade.get("exit_time"),
            "reason":        trade.get("reason"),
            "status":        trade.get("reason", "CLOSED").upper(),
            # Fields MỚI
            "position_size_pct": trade.get("position_size_pct", 0.0),
            "risk_amount_usd":   trade.get("risk_amount_usd", 0.0),
            "expected_value_r":  trade.get("expected_value_r", 0.0),
            "market_regime":     trade.get("market_regime", "unknown"),
            "session_at_entry":  trade.get("session_name", "unknown"),
            "family":            trade.get("family", "unknown"),
        })

    return {
        "overview":       overview,
        "symbols":        symbols_list,
        "paper_positions": {
            "positions": formatted_positions,
            "history":   formatted_history,
            "balance":   summary.get("balance"),
            "equity":    summary.get("equity"),
        },
        "telemetry": telemetry_metrics,
    }


# ─────────────────────────────────────────────────────────────────────
# get_signals_payload  (SỬA — thêm Quality Gate enrichment)
# ─────────────────────────────────────────────────────────────────────

def get_signals_payload() -> Dict[str, Any]:
    snap = globals.engine.snapshot()

    # Lấy QualifiedSignal history từ broker (index theo signal_id)
    qs_map: Dict[str, Any] = {}
    try:
        for qs_dict in globals.broker.get_qualified_signals(limit=200):
            qs_map[qs_dict.get("signal_id", "")] = qs_dict
    except Exception:
        pass

    signals_list = []
    for symbol, state in snap.items():
        for name, sig in state.get("signals", {}).items():
            # Quality Gate enrichment nếu có
            qs = qs_map.get(name, {})

            signals_list.append({
                # ── Fields cũ (giữ nguyên) ──
                "symbol":               symbol,
                "signal_id":            name,
                "family":               sig.get("template_family"),
                "direction":            sig.get("direction", "both"),
                "triggered":            bool(sig.get("triggered")),
                "confirmed":            bool(sig.get("confirmed")),
                "invalidated":          bool(sig.get("invalidated")),
                "active":               bool(sig.get("active")),
                "confirmation_score":   sig.get("confirmation_score", 0.0),
                "invalidation_score":   sig.get("invalidation_score", 0.0),
                "quality_tier":         sig.get("quality_tier", "A"),
                "regime_fit":           bool(sig.get("why", {}).get("regime_ok")),
                "entry_side":           state.get("strategies", {}).get(name, {}).get("entry_side")
                                        if sig.get("active") else None,
                "thesis":               qs.get("thesis", sig.get("thesis")),
                "entry_logic_summary":  sig.get("entry_logic_summary"),
                "confirmation_summary": sig.get("confirmation_summary"),
                "invalidation_summary": sig.get("invalidation_summary"),
                "updated_at":           state.get("updated_at"),

                # ── Fields MỚI từ QualifiedSignal ──
                "gate_qualified":        bool(qs),
                "confidence_score":      qs.get("confidence_score",   sig.get("confidence_score", 0.0)),
                "risk_reward_ratio":     qs.get("risk_reward_ratio",  0.0),
                "entry_price":           qs.get("entry_price",        0.0),
                "stop_loss":             qs.get("stop_loss",          0.0),
                "take_profit":           qs.get("take_profit",        0.0),
                "position_size_pct":     qs.get("position_size_pct",  0.0),
                "position_size_usd":     qs.get("position_size_usd",  0.0),
                "risk_amount_usd":       qs.get("risk_amount_usd",    0.0),
                "expected_value_r":      qs.get("expected_value_r",   0.0),
                "market_regime":         qs.get("market_regime",      "unknown"),
                "btc_structure":         qs.get("btc_structure",      "neutral"),
                "session_name":          qs.get("session_name",       "unknown"),
                "qualified_at":          qs.get("qualified_at"),
                "gate_layers":           qs.get("layer_results", []),
            })

    return {"signals": signals_list}


# ─────────────────────────────────────────────────────────────────────
# get_signal_detail  (SỬA — thêm gate enrichment)
# ─────────────────────────────────────────────────────────────────────

def get_signal_detail(symbol: str, signal_id: str) -> Optional[Dict[str, Any]]:
    snap = globals.engine.snapshot()
    state = snap.get(symbol)
    if not state:
        return None
    sig = state.get("signals", {}).get(signal_id)
    if not sig:
        return None

    # Lookup QualifiedSignal
    qs: Dict[str, Any] = {}
    try:
        for qs_dict in globals.broker.get_qualified_signals(limit=200):
            if qs_dict.get("signal_id") == signal_id:
                qs = qs_dict
                break
    except Exception:
        pass

    return {
        # ── Fields cũ ──
        "symbol":               symbol,
        "signal_id":            signal_id,
        "family":               sig.get("template_family"),
        "direction":            sig.get("direction", "both"),
        "triggered":            bool(sig.get("triggered")),
        "confirmed":            bool(sig.get("confirmed")),
        "invalidated":          bool(sig.get("invalidated")),
        "active":               bool(sig.get("active")),
        "confirmation_score":   sig.get("confirmation_score", 0.0),
        "invalidation_score":   sig.get("invalidation_score", 0.0),
        "quality_tier":         sig.get("quality_tier", "A"),
        "regime_fit":           bool(sig.get("why", {}).get("regime_ok")),
        "entry_side":           state.get("strategies", {}).get(signal_id, {}).get("entry_side")
                                if sig.get("active") else None,
        "thesis":               qs.get("thesis", sig.get("thesis")),
        "entry_logic_summary":  sig.get("entry_logic_summary"),
        "confirmation_summary": sig.get("confirmation_summary"),
        "invalidation_summary": sig.get("invalidation_summary"),
        "why":                  sig.get("why", {}),
        "updated_at":           state.get("updated_at"),

        # ── Fields MỚI ──
        "gate_qualified":        bool(qs),
        "entry_price":           qs.get("entry_price",       sig.get("entry_price", 0.0)),
        "stop_loss":             qs.get("stop_loss",         sig.get("stop_loss",   0.0)),
        "take_profit":           qs.get("take_profit",       sig.get("take_profit", 0.0)),
        "confidence_score":      qs.get("confidence_score",  0.0),
        "risk_reward_ratio":     qs.get("risk_reward_ratio", 0.0),
        "position_size_pct":     qs.get("position_size_pct", 0.0),
        "position_size_usd":     qs.get("position_size_usd", 0.0),
        "risk_amount_usd":       qs.get("risk_amount_usd",   0.0),
        "expected_value_r":      qs.get("expected_value_r",  0.0),
        "market_regime":         qs.get("market_regime",     "unknown"),
        "btc_structure":         qs.get("btc_structure",     "neutral"),
        "session_name":          qs.get("session_name",      "unknown"),
        "qualified_at":          qs.get("qualified_at"),
        "gate_layers":           qs.get("layer_results", []),
    }


# ─────────────────────────────────────────────────────────────────────
# get_gate_payload  (FUNCTION MỚI HOÀN TOÀN)
# ─────────────────────────────────────────────────────────────────────

def get_gate_payload() -> Dict[str, Any]:
    """
    Trả về toàn bộ Quality Gate state cho dashboard tab mới.
    Bao gồm: portfolio state, cooldown map, qualified signal feed,
    và config hiện tại.
    """
    gate = _gate()
    gate_sum = _gate_summary()

    # Qualified signal feed (50 gần nhất)
    qualified_feed: list = []
    try:
        qualified_feed = globals.broker.get_qualified_signals(limit=50)
    except Exception:
        pass

    # Cooldown map (key → remaining seconds)
    cooldown_info: list = []
    if gate is not None:
        import time as _time
        now_ts = _time.time()
        cd_seconds = gate._cfg.portfolio.cooldown_seconds
        for key, last_fire in list(gate._cooldown.items()):
            remaining = max(0.0, cd_seconds - (now_ts - last_fire))
            cooldown_info.append({
                "cooldown_key": key,
                "remaining_seconds": round(remaining, 1),
                "total_seconds": cd_seconds,
                "pct_elapsed": round((1 - remaining / cd_seconds) * 100, 1) if cd_seconds > 0 else 100.0,
            })
        cooldown_info.sort(key=lambda x: x["remaining_seconds"], reverse=True)

    # Active signal slots
    active_slots: list = []
    if gate is not None:
        for sig_id, (sym, cluster) in list(gate._active_signals.items()):
            active_slots.append({
                "signal_id": sig_id,
                "symbol": sym,
                "cluster": cluster,
            })

    # Gate config summary
    gate_config: Dict[str, Any] = {}
    if gate is not None:
        cfg = gate._cfg
        gate_config = {
            "session_filter_enabled":     cfg.session.enabled,
            "regime_filter_enabled":      cfg.regime.enabled,
            "portfolio_filter_enabled":   cfg.portfolio.enabled,
            "statistical_filter_enabled": cfg.statistical.enabled,
            "sizing_enabled":             cfg.sizing.enabled,
            "anchor_symbol":              cfg.regime.anchor_symbol,
            "cooldown_seconds":           cfg.portfolio.cooldown_seconds,
            "max_concurrent_signals":     cfg.portfolio.max_concurrent_signals,
            "max_signals_per_cluster":    cfg.portfolio.max_signals_per_cluster,
            "max_portfolio_heat_pct":     cfg.portfolio.max_portfolio_heat_pct,
            "min_confidence":             cfg.statistical.min_confidence,
            "min_rr_ratio":               cfg.statistical.min_rr_ratio,
            "min_ev_r":                   cfg.statistical.min_ev_r,
            "kelly_fraction":             cfg.sizing.kelly_fraction,
            "min_position_pct":           cfg.sizing.min_position_pct,
            "max_position_pct":           cfg.sizing.max_position_pct,
            "account_equity_usd":         cfg.sizing.account_equity,
            "family_win_rates":           cfg.statistical.family_win_rates,
            "family_regime_map":          cfg.regime.family_regime_map,
            "correlation_clusters":       cfg.portfolio.correlation_clusters,
        }

    return {
        "gate_summary":      gate_sum,
        "active_slots":      active_slots,
        "cooldown_map":      cooldown_info,
        "qualified_feed":    qualified_feed,
        "gate_config":       gate_config,
    }


# ─────────────────────────────────────────────────────────────────────
# get_rejections_payload  (FUNCTION MỚI HOÀN TOÀN)
# ─────────────────────────────────────────────────────────────────────

def get_rejections_payload(limit: int = 50) -> Dict[str, Any]:
    """
    Trả về danh sách GateRejection gần nhất.
    Hữu ích để debug tại sao signal bị block.
    """
    gate = _gate()
    if gate is None:
        return {"rejections": [], "total_count": 0, "gate_enabled": False}

    rejections_raw = list(gate.rejection_log)[-limit:]
    rejections_raw.reverse()   # mới nhất trước

    rejections = []
    for r in rejections_raw:
        try:
            d = r.to_dict()
            # Thêm layer breakdown để debug
            d["layer_breakdown"] = [
                {
                    "layer":   lr.layer_name,
                    "verdict": lr.verdict,
                    "reason":  lr.reason,
                }
                for lr in r.layer_results
            ]
            rejections.append(d)
        except Exception:
            pass

    # Aggregate stats
    block_by_layer: Dict[str, int] = {}
    block_by_reason: Dict[str, int] = {}
    block_by_symbol: Dict[str, int] = {}
    for r in rejections:
        layer = r.get("blocked_by_layer", "unknown")
        reason = r.get("block_reason", "unknown")
        symbol = r.get("symbol", "unknown")
        block_by_layer[layer]   = block_by_layer.get(layer, 0) + 1
        block_by_reason[reason] = block_by_reason.get(reason, 0) + 1
        block_by_symbol[symbol] = block_by_symbol.get(symbol, 0) + 1

    return {
        "rejections":       rejections,
        "total_count":      len(list(gate.rejection_log)),
        "returned_count":   len(rejections),
        "gate_enabled":     gate._cfg.enabled,
        "stats": {
            "by_layer":  block_by_layer,
            "by_reason": block_by_reason,
            "by_symbol": block_by_symbol,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# get_dashboard_payload  (SỬA — thêm gate section)
# ─────────────────────────────────────────────────────────────────────

def get_dashboard_payload() -> Dict[str, Any]:
    """Backward-compatible combined payload. Thêm gate summary."""
    ov   = get_overview_payload()
    sigs = get_signals_payload()

    snap = globals.engine.snapshot()
    full_signals = []
    for s in sigs["signals"]:
        symbol = s["symbol"]
        sig_id = s["signal_id"]
        sig_data = snap.get(symbol, {}).get("signals", {}).get(sig_id, {})
        s_copy = dict(s)
        s_copy["why"] = sig_data.get("why", {})    # backward compat
        full_signals.append(s_copy)

    payload = dict(ov)
    payload["signals"] = full_signals

    # THÊM: gate summary tại top level để frontend dễ đọc
    payload["gate"] = _gate_summary()

    return payload
