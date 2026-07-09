from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from risk_models import merge_risk_config


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strategy_limit(config: Dict[str, Any], mapping_key: str, strategy_name: str, default_key: str = 'default') -> float:
    mapping = config.get(mapping_key, {}) or {}
    return float(mapping.get(strategy_name, mapping.get(default_key, 0.0)))


def compute_position_size(
    symbol: str,
    last_price: float,
    indicators: dict,
    risk_config: dict,
    portfolio_state: dict,
    regime_state: dict | None = None
) -> dict:
    """
    Computes target_quantity using one of the configured sizing models.
    Supports ATR, Kelly Criterion, and Fixed sizing.
    """
    balance = float(portfolio_state.get('balance', risk_config.get('account_equity', 10000.0)))
    
    sizing_model = risk_config.get('sizing_model', 'atr')
    risk_pct_per_trade = float(risk_config.get('risk_pct_per_trade', 0.01))
    atr_stop_multiplier = float(risk_config.get('atr_stop_multiplier', 1.5))
    min_quantity = float(risk_config.get('min_quantity', 0.001))
    max_quantity = float(risk_config.get('max_quantity', 0.5))
    max_position_pct = float(risk_config.get('max_position_pct', 0.10))
    kelly_fraction = float(risk_config.get('kelly_fraction', 0.25))
    max_kelly_pct = float(risk_config.get('max_kelly_pct', 0.05))
    min_trades_for_kelly = int(risk_config.get('min_trades_for_kelly', 10))
    fixed_quantity = float(risk_config.get('fixed_quantity', 0.01))

    sizing_model_used = sizing_model
    risk_amount_usd = 0.0
    stop_distance_usd = None
    atr_pct_14 = None
    kelly_f = None
    notes = ""

    if last_price <= 0:
        sizing_model_used = 'fixed'
        notes = "last_price <= 0; fallback to fixed sizing."
        target_quantity = fixed_quantity
    else:
        if sizing_model == 'atr':
            atr_pct_14 = indicators.get('atr_pct_14')
            if atr_pct_14 is None or atr_pct_14 <= 0:
                sizing_model_used = 'fixed'
                notes = "atr_pct_14 <= 0 or None; fallback to fixed sizing."
                target_quantity = fixed_quantity
            else:
                risk_amount_usd = balance * risk_pct_per_trade
                atr_distance = atr_pct_14 * last_price
                stop_distance_usd = atr_distance * atr_stop_multiplier
                if stop_distance_usd <= 0:
                    sizing_model_used = 'fixed'
                    notes = "stop_distance_usd <= 0; fallback to fixed sizing."
                    target_quantity = fixed_quantity
                else:
                    target_quantity = risk_amount_usd / stop_distance_usd
                    notes = f"ATR sizing. Risk amount: {risk_amount_usd:.2f}, Stop distance: {stop_distance_usd:.4f}"

        elif sizing_model == 'kelly':
            if regime_state:
                # Regime-based Kelly sizing
                regime_confidence = float(regime_state.get('confidence', 0.65))
                family_win_rates = {
                    "continuation": 0.52,
                    "breakout": 0.48,
                    "mean_reversion": 0.58,
                    "funding_reversion": 0.55,
                    "oi_reversal": 0.50
                }
                allowed_fams = regime_state.get('allowed_signal_families', [])
                win_rate = 0.50
                for f_name in allowed_fams:
                    if f_name in family_win_rates:
                        win_rate = family_win_rates[f_name]
                        break
                
                rr = float(risk_config.get('rr_ratio', 2.0))
                
                # Kelly formula: f* = (p * R - q) / R
                kelly_f = ((win_rate * rr - (1.0 - win_rate)) / rr) if rr > 0.0 else 0.0
                
                # Scale by regime confidence and Kelly fraction
                fractional_kelly = kelly_f * kelly_fraction * regime_confidence
                kelly_risk_fraction = max(0.0, min(fractional_kelly, max_kelly_pct))
                
                risk_amount_usd = balance * kelly_risk_fraction
                atr_val = indicators.get('atr_pct_14') or indicators.get('atr_14_pct')
                if atr_val and atr_val > 0:
                    # If it's atr_14_pct, it's already in percent (e.g. 0.25 for 0.25%), convert if needed
                    atr_pct = atr_val / 100.0 if atr_val > 0.5 else atr_val
                    stop_distance_usd = atr_pct * last_price * atr_stop_multiplier
                else:
                    stop_distance_usd = last_price * 0.015 * atr_stop_multiplier
                
                target_quantity = risk_amount_usd / stop_distance_usd if stop_distance_usd > 0 else fixed_quantity
                notes = f"Regime Kelly. WinRate: {win_rate:.2f}, Conf: {regime_confidence:.2f}, kelly_f: {kelly_f:.4f}, target_qty: {target_quantity:.6f}"
            else:
                # Fallback to trade history-based Kelly
                trade_count = 0
                win_rate = 0.5
                avg_win_pct = 0.015
                avg_loss_pct = 0.01

                trade_history = portfolio_state.get('trade_history', portfolio_state.get('history', []))
                if trade_history:
                    trade_count = len(trade_history)
                    wins = [t for t in trade_history if t.get('pnl', 0.0) > 0]
                    losses = [t for t in trade_history if t.get('pnl', 0.0) <= 0]
                    win_rate = len(wins) / trade_count if trade_count > 0 else 0.5
                    
                    win_pcts = []
                    for t in wins:
                        entry_val = t.get('entry_price', 0) * t.get('quantity', 0)
                        if entry_val > 0:
                            win_pcts.append(t.get('pnl', 0.0) / entry_val)
                    avg_win_pct = sum(win_pcts) / len(win_pcts) if win_pcts else 0.015
                    
                    loss_pcts = []
                    for t in losses:
                        entry_val = t.get('entry_price', 0) * t.get('quantity', 0)
                        if entry_val > 0:
                            loss_pcts.append(abs(t.get('pnl', 0.0)) / entry_val)
                    avg_loss_pct = sum(loss_pcts) / len(loss_pcts) if loss_pcts else 0.01

                if 'trade_count' in portfolio_state:
                    trade_count = int(portfolio_state['trade_count'])
                if 'win_rate' in portfolio_state:
                    win_rate = float(portfolio_state['win_rate'])
                if 'avg_win_pct' in portfolio_state:
                    avg_win_pct = float(portfolio_state['avg_win_pct'])
                if 'avg_loss_pct' in portfolio_state:
                    avg_loss_pct = float(portfolio_state['avg_loss_pct'])

                if trade_count < min_trades_for_kelly:
                    sizing_model_used = 'atr'
                    atr_pct_14 = indicators.get('atr_pct_14')
                    if atr_pct_14 is None or atr_pct_14 <= 0:
                        sizing_model_used = 'fixed'
                        notes = f"Kelly fallback to ATR, but atr_pct_14 <= 0 or None; fallback to fixed sizing (trades: {trade_count} < {min_trades_for_kelly})."
                        target_quantity = fixed_quantity
                    else:
                        risk_amount_usd = balance * risk_pct_per_trade
                        atr_distance = atr_pct_14 * last_price
                        stop_distance_usd = atr_distance * atr_stop_multiplier
                        if stop_distance_usd <= 0:
                            sizing_model_used = 'fixed'
                            notes = "stop_distance_usd <= 0; fallback to fixed sizing."
                            target_quantity = fixed_quantity
                        else:
                            target_quantity = risk_amount_usd / stop_distance_usd
                            notes = f"Kelly fallback to ATR (trades: {trade_count} < {min_trades_for_kelly}). Risk amount: {risk_amount_usd:.2f}, Stop distance: {stop_distance_usd:.4f}"
                else:
                    if avg_win_pct <= 0.0:
                        kelly_f = 0.0
                    else:
                        kelly_f = ((win_rate * avg_win_pct - (1.0 - win_rate) * avg_loss_pct) / avg_win_pct) if avg_win_pct > 0.0 else 0.0
                    
                    fractional_kelly = kelly_f * kelly_fraction
                    kelly_risk_fraction = max(0.0, min(fractional_kelly, max_kelly_pct))
                    risk_amount_usd = balance * kelly_risk_fraction
                    target_quantity = risk_amount_usd / last_price
                    notes = f"Kelly sizing. kelly_f: {kelly_f:.4f}, fractional: {fractional_kelly:.4f}, risk fraction: {kelly_risk_fraction:.4f}"

        else:
            sizing_model_used = 'fixed'
            target_quantity = fixed_quantity
            notes = f"Fixed sizing: {fixed_quantity}"

        if sizing_model_used != 'fixed':
            max_qty_by_pct = max_position_pct * balance / last_price
            target_quantity = min(target_quantity, max_qty_by_pct)
            target_quantity = min(target_quantity, max_quantity)
            target_quantity = max(target_quantity, min_quantity)
            notes += f" | Capped at range [{min_quantity}, {max_quantity}] and max_position_pct limit: {max_qty_by_pct:.6f}"

    return {
        "target_quantity": round(float(target_quantity), 8),
        "sizing_model_used": sizing_model_used,
        "risk_amount_usd": round(float(risk_amount_usd), 8),
        "stop_distance_usd": round(float(stop_distance_usd), 8) if stop_distance_usd is not None else None,
        "atr_pct_14": float(atr_pct_14) if atr_pct_14 is not None else None,
        "kelly_f": float(kelly_f) if kelly_f is not None else None,
        "notes": notes
    }


def build_risk_packet_v1(
    symbol: str,
    state: Dict[str, Any],
    strategy_name: str,
    strategy_state: Dict[str, Any],
    risk_config: Dict[str, Any] | None = None,
    portfolio_state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    config = merge_risk_config(risk_config)
    portfolio = dict(config.get('portfolio_state', {}))
    if portfolio_state:
        portfolio.update(portfolio_state)

    regime_state = state.get('regime_state', {}) or {}
    factors = state.get('factors', {}) or {}
    indicators = state.get('indicators', {}) or {}
    last_price = state.get('last_price') or state.get('last_trade') or strategy_state.get('last_price')
    tradable = bool(regime_state.get('tradable', False))
    logic_ready = bool(strategy_state.get('logic_ready', strategy_state.get('status') == 'candidate'))
    spread_bps = indicators.get('SpreadBps', factors.get('spread_bps', 0.0)) or 0.0
    micro_volatility = indicators.get('MicroVolatility', factors.get('micro_volatility_20', 0.0)) or 0.0
    trade_flow_imbalance = indicators.get('TradeFlowImbalance', factors.get('trade_flow_imbalance_20', 0.0)) or 0.0
    account_equity = float(config.get('account_equity', 0.0))
    cash_available = float(config.get('cash_available', account_equity))
    max_symbol_notional_fraction = float(config.get('max_symbol_notional_fraction', 0.0))
    max_portfolio_gross_fraction = float(config.get('max_portfolio_gross_fraction', 0.0))
    per_trade_risk_fraction = float(config.get('per_trade_risk_fraction', 0.0))
    max_concurrent_candidates = int(config.get('max_concurrent_candidates', 0))
    kill_switch = dict(config.get('kill_switch', {}))

    rejection_reasons = []
    advisory_flags = []

    if kill_switch.get('active'):
        rejection_reasons.append('kill_switch_active')
    if not logic_ready:
        rejection_reasons.append('strategy_not_active')
    # regime_not_tradable is now gated upstream by logic_ready + family_allowed checks.
    # Only block here if regime is completely non-tradable AND strategy is not logic_ready.
    # This avoids double-blocking the new 'cautious' tier.
    if not last_price:
        rejection_reasons.append('missing_last_price')

    spread_limit = _strategy_limit(config, 'spread_bps_limits', strategy_name)
    if spread_limit and spread_bps > spread_limit:
        rejection_reasons.append('spread_above_limit')
    elif spread_limit and spread_bps > spread_limit * 0.75:
        advisory_flags.append('spread_elevated')

    micro_limit = _strategy_limit(config, 'micro_volatility_limits', strategy_name)
    if micro_limit and micro_volatility > micro_limit:
        rejection_reasons.append('micro_volatility_above_limit')
    elif micro_limit and micro_volatility > micro_limit * 0.75:
        advisory_flags.append('micro_volatility_elevated')

    if portfolio.get('active_positions_count', 0) >= max_concurrent_candidates > 0:
        rejection_reasons.append('max_concurrent_candidates_reached')

    gross_exposure = float(portfolio.get('gross_exposure', 0.0) or 0.0)
    if gross_exposure >= max_portfolio_gross_fraction > 0:
        rejection_reasons.append('portfolio_gross_limit_reached')

    session_realized_pnl = float(portfolio.get('session_realized_pnl', 0.0) or 0.0)
    if account_equity and session_realized_pnl <= -(account_equity * float(config.get('session_loss_limit_fraction', 0.0))):
        rejection_reasons.append('session_loss_limit_breached')

    # Position Sizing
    sizing_result = compute_position_size(
        symbol=symbol,
        last_price=last_price or 0.0,
        indicators=indicators,
        risk_config=config,
        portfolio_state=portfolio,
        regime_state=regime_state
    )
    target_quantity = sizing_result["target_quantity"]
    target_notional = target_quantity * last_price if last_price and target_quantity else 0.0
    max_loss_budget = sizing_result["risk_amount_usd"] or (account_equity * per_trade_risk_fraction)

    # Stop Loss & Suggested SL/TP
    entry_side = strategy_state.get('entry_side', 'long')
    stop_distance_fraction = max(float(strategy_state.get('stop_distance_fraction', 0.0) or 0.0), float(micro_volatility or 0.0) * 3.0, 0.001)
    stop_price = None
    take_profit_price = None

    if last_price:
        # Determine base Stop/TP multiplier and ratio
        atr_stop_multiplier = float(config.get('atr_stop_multiplier', 1.5))
        
        # 1. Dynamic R:R Targets (ADX-based SL/TP scaling)
        adx_14 = indicators.get('adx_14', 0.0)
        if adx_14 > 30.0:
            rr_ratio = 3.5  # Strong trend: run winners
        elif adx_14 < 18.0:
            rr_ratio = 1.3  # Choppy: tight take profits
        else:
            rr_ratio = float(config.get('rr_ratio', 2.0))

        # Check if ATR is available
        atr_val = sizing_result.get("atr_pct_14") or indicators.get('atr_pct_14') or indicators.get('atr_14_pct')
        if atr_val is not None and atr_val > 0:
            atr_pct_14 = atr_val / 100.0 if atr_val > 0.5 else atr_val
            
            # 2. Spread-buffered Stop Loss
            suggested_stop_loss_pct = atr_pct_14 * atr_stop_multiplier + (spread_bps / 10000.0)
            suggested_take_profit_pct = suggested_stop_loss_pct * rr_ratio
            
            stop_distance_fraction = suggested_stop_loss_pct
            stop_price = last_price * (1 - suggested_stop_loss_pct) if entry_side == 'long' else last_price * (1 + suggested_stop_loss_pct)
            take_profit_price = last_price * (1 + suggested_take_profit_pct) if entry_side == 'long' else last_price * (1 - suggested_take_profit_pct)
        else:
            # Fallback to standard stop_distance_fraction, adding spread buffer
            suggested_stop_loss_pct = stop_distance_fraction + (spread_bps / 10000.0)
            suggested_take_profit_pct = suggested_stop_loss_pct * rr_ratio
            
            stop_distance_fraction = suggested_stop_loss_pct
            stop_price = last_price * (1 - suggested_stop_loss_pct) if entry_side == 'long' else last_price * (1 + suggested_stop_loss_pct)
            take_profit_price = last_price * (1 + suggested_take_profit_pct) if entry_side == 'long' else last_price * (1 - suggested_take_profit_pct)

    if stop_distance_fraction > 0.02:
        advisory_flags.append('wide_stop_distance')
    if abs(trade_flow_imbalance) > 0.70:
        advisory_flags.append('one_sided_trade_flow')
    if target_quantity <= 0:
        rejection_reasons.append('zero_target_quantity')

    allow_entry = len(rejection_reasons) == 0
    if kill_switch.get('active') or 'session_loss_limit_breached' in rejection_reasons:
        risk_status = 'FLATTEN_ONLY'
        allow_entry = False
    elif allow_entry and advisory_flags:
        risk_status = 'ALLOW_WITH_WARNINGS'
    elif allow_entry:
        risk_status = 'ALLOW'
    else:
        risk_status = 'BLOCK'

    packet = {
        'symbol': symbol,
        'signal_name': strategy_name,
        'risk_status': risk_status,
        'allow_entry': allow_entry,
        'rejection_reasons': rejection_reasons,
        'advisory_flags': advisory_flags,
        'sizing_mode': sizing_result["sizing_model_used"],
        'target_notional': round(float(target_notional), 8),
        'target_quantity': round(float(target_quantity), 8),
        'max_loss_budget': round(float(max_loss_budget), 8),
        'position_sizing': sizing_result,
        'stop_policy': {
            'stop_policy_type': 'volatility_scaled_stop' if sizing_result["sizing_model_used"] != "atr" else 'atr_scaled_stop',
            'initial_stop_price': round(float(stop_price), 8) if stop_price else None,
            'stop_distance_fraction': round(float(stop_distance_fraction), 8),
            'stop_reason': 'default_v1_volatility_scaled' if sizing_result["sizing_model_used"] != "atr" else 'atr_stop_multiplier_scaled',
            'trailing_policy': None,
        },
        'take_profit_policy': {
            'policy_type': 'fixed_rr_target' if sizing_result["sizing_model_used"] != "atr" else 'atr_rr_target',
            'rr_multiple': float(config.get('rr_ratio', 2.0)),
        },
        'kill_switch_state': kill_switch,
        'exposure_snapshot': {
            'account_equity': account_equity,
            'cash_available': cash_available,
            'gross_exposure': gross_exposure,
            'net_exposure': float(portfolio.get('net_exposure', 0.0) or 0.0),
            'active_positions_count': int(portfolio.get('active_positions_count', 0) or 0),
            'symbol_exposure': (portfolio.get('symbol_exposure', {}) or {}).get(symbol, 0.0),
        },
        'execution_constraints': {
            'spread_bps': round(float(spread_bps), 8),
            'spread_limit_bps': round(float(spread_limit), 8),
            'micro_volatility': round(float(micro_volatility), 8),
            'micro_volatility_limit': round(float(micro_limit), 8),
            'trade_flow_imbalance': round(float(trade_flow_imbalance), 8),
        },
        'updated_at': now_iso(),
    }

    if sizing_result["sizing_model_used"] == "atr" and sizing_result["atr_pct_14"] is not None:
        atr_pct_14 = sizing_result["atr_pct_14"]
        atr_stop_multiplier = float(config.get('atr_stop_multiplier', 1.5))
        rr_ratio = float(config.get('rr_ratio', 2.0))
        suggested_stop_loss_pct = atr_pct_14 * atr_stop_multiplier
        suggested_take_profit_pct = suggested_stop_loss_pct * rr_ratio
        
        packet["suggested_stop_loss_pct"] = round(float(suggested_stop_loss_pct), 8)
        packet["suggested_take_profit_pct"] = round(float(suggested_take_profit_pct), 8)
        if take_profit_price is not None:
            packet["take_profit_price"] = round(float(take_profit_price), 8)

    return packet
