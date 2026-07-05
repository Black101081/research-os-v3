from __future__ import annotations

import globals
from typing import Dict, Any, List

def get_overview_payload() -> Dict[str, Any]:
    snap = globals.engine.snapshot()
    summary = globals.broker.get_summary()
    telemetry_metrics = globals.telemetry.get_metrics()
    
    # 1. Overview
    active_sig_count = 0
    confirmed_sig_count = 0
    execution_ready_count = 0
    
    for symbol, state in snap.items():
        for signal_name, signal_payload in state.get('signals', {}).items():
            if signal_payload.get('active'):
                active_sig_count += 1
            if signal_payload.get('confirmed'):
                confirmed_sig_count += 1
        for strat_name, strat_payload in state.get('strategies', {}).items():
            if strat_payload.get('execution_ready'):
                execution_ready_count += 1

    overview = {
        "mode": globals.trading_mode,
        "kill_switch_active": globals.kill_switch_active,
        "latency_ms": round(telemetry_metrics.get("avg_latency_ms", 0.0), 2),
        "error_rate": round(telemetry_metrics.get("error_rate_pct", 0.0), 2),
        "uptime_seconds": telemetry_metrics.get("uptime_seconds", 0),
        "active_signal_count": active_sig_count,
        "confirmed_signal_count": confirmed_sig_count,
        "execution_ready_count": execution_ready_count,
        "open_positions_count": summary.get("active_positions_count", 0),
        "symbols": globals.CONFIG['symbols'],
        "candle_interval": globals.CONFIG['candle_interval']
    }

    # 2. Symbols overview
    symbols_list = []
    for symbol in globals.CONFIG['symbols']:
        state = snap.get(symbol, {})
        if not state:
            continue
        
        regime_state = state.get('regime_state', {})
        signals = state.get('signals', {})
        
        triggered_cnt = 0
        confirmed_cnt = 0
        active_cnt = 0
        invalidated_cnt = 0
        top_signals = []
        
        for name, sig in signals.items():
            if sig.get('triggered'):
                triggered_cnt += 1
            if sig.get('confirmed'):
                confirmed_cnt += 1
            if sig.get('active'):
                active_cnt += 1
                top_signals.append(name)
            if sig.get('invalidated'):
                invalidated_cnt += 1
                
        symbols_list.append({
            "symbol": symbol,
            "last_trade": state.get('last_trade') or state.get('mid'),
            "mid": state.get('mid'),
            "updated_at": state.get('updated_at'),
            "regime": regime_state.get('regime'),
            "regime_confidence": regime_state.get('confidence', 0.0),
            "tradable": regime_state.get('tradable', False),
            "bars_loaded": len(state.get('bars', [])),
            "signal_summary": {
                "total": len(signals),
                "triggered": triggered_cnt,
                "confirmed": confirmed_cnt,
                "active": active_cnt,
                "invalidated": invalidated_cnt
            },
            "top_signals": top_signals
        })

    # 4. Positions & Trade History
    formatted_positions = []
    for pos in summary.get('positions', []):
        formatted_positions.append({
            "symbol": pos.get('symbol'),
            "signal_source": pos.get('signal_source', 'unknown'),
            "direction": pos.get('direction'),
            "quantity": pos.get('quantity'),
            "entry_price": pos.get('entry_price'),
            "current_price": pos.get('current_price'),
            "unrealized_pnl": pos.get('unrealized_pnl', 0.0),
            "stop_loss": pos.get('stop_loss'),
            "take_profit": pos.get('take_profit'),
            "entry_time": pos.get('entry_time'),
            "status": "OPEN"
        })

    formatted_history = []
    for trade in summary.get('trade_history', []):
        formatted_history.append({
            "symbol": trade.get('symbol'),
            "signal_source": trade.get('signal_source', 'unknown'),
            "direction": trade.get('direction'),
            "quantity": trade.get('quantity'),
            "entry_price": trade.get('entry_price'),
            "exit_price": trade.get('exit_price'),
            "pnl": trade.get('pnl', 0.0),
            "entry_time": trade.get('entry_time'),
            "exit_time": trade.get('exit_time'),
            "reason": trade.get('reason'),
            "status": trade.get('reason', 'CLOSED').upper()
        })

    return {
        "overview": overview,
        "symbols": symbols_list,
        "paper_positions": {
            "positions": formatted_positions,
            "history": formatted_history,
            "balance": summary.get('balance'),
            "equity": summary.get('equity')
        },
        "telemetry": telemetry_metrics
    }

def get_signals_payload() -> Dict[str, Any]:
    snap = globals.engine.snapshot()
    signals_list = []
    for symbol, state in snap.items():
        signals = state.get('signals', {})
        for name, sig in signals.items():
            signals_list.append({
                "symbol": symbol,
                "signal_id": name,
                "family": sig.get('template_family'),
                "direction": sig.get('direction', 'both'),
                "triggered": bool(sig.get('triggered')),
                "confirmed": bool(sig.get('confirmed')),
                "invalidated": bool(sig.get('invalidated')),
                "active": bool(sig.get('active')),
                "confirmation_score": sig.get('confirmation_score', 0.0),
                "invalidation_score": sig.get('invalidation_score', 0.0),
                "quality_tier": sig.get('quality_tier', 'A'),
                "regime_fit": bool(sig.get('why', {}).get('regime_ok')),
                "entry_side": state.get('strategies', {}).get(name, {}).get('entry_side') if sig.get('active') else None,
                "thesis": sig.get('thesis'),
                "entry_logic_summary": sig.get('entry_logic_summary'),
                "confirmation_summary": sig.get('confirmation_summary'),
                "invalidation_summary": sig.get('invalidation_summary'),
                "updated_at": state.get('updated_at')
            })
    return {"signals": signals_list}

def get_signal_detail(symbol: str, signal_id: str) -> Dict[str, Any] | None:
    snap = globals.engine.snapshot()
    state = snap.get(symbol)
    if not state:
        return None
    signals = state.get('signals', {})
    sig = signals.get(signal_id)
    if not sig:
        return None
    return {
        "symbol": symbol,
        "signal_id": signal_id,
        "family": sig.get('template_family'),
        "direction": sig.get('direction', 'both'),
        "triggered": bool(sig.get('triggered')),
        "confirmed": bool(sig.get('confirmed')),
        "invalidated": bool(sig.get('invalidated')),
        "active": bool(sig.get('active')),
        "confirmation_score": sig.get('confirmation_score', 0.0),
        "invalidation_score": sig.get('invalidation_score', 0.0),
        "quality_tier": sig.get('quality_tier', 'A'),
        "regime_fit": bool(sig.get('why', {}).get('regime_ok')),
        "entry_side": state.get('strategies', {}).get(signal_id, {}).get('entry_side') if sig.get('active') else None,
        "thesis": sig.get('thesis'),
        "entry_logic_summary": sig.get('entry_logic_summary'),
        "confirmation_summary": sig.get('confirmation_summary'),
        "invalidation_summary": sig.get('invalidation_summary'),
        "why": sig.get('why', {}),
        "updated_at": state.get('updated_at')
    }

def get_dashboard_payload() -> Dict[str, Any]:
    # Maintain the old endpoint compatibility
    ov = get_overview_payload()
    sigs = get_signals_payload()
    
    # Merge signals and add why back for backward compatibility
    snap = globals.engine.snapshot()
    full_signals = []
    for s in sigs['signals']:
        symbol = s['symbol']
        sig_id = s['signal_id']
        sig_data = snap.get(symbol, {}).get('signals', {}).get(sig_id, {})
        s_copy = dict(s)
        s_copy['why'] = sig_data.get('why', {})
        full_signals.append(s_copy)

    payload = dict(ov)
    payload['signals'] = full_signals
    return payload
