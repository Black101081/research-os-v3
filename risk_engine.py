from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from risk_models import merge_risk_config


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strategy_limit(config: Dict[str, Any], mapping_key: str, strategy_name: str, default_key: str = 'default') -> float:
    mapping = config.get(mapping_key, {}) or {}
    return float(mapping.get(strategy_name, mapping.get(default_key, 0.0)))


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
    if not tradable:
        rejection_reasons.append('regime_not_tradable')
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

    stop_distance_fraction = max(float(strategy_state.get('stop_distance_fraction', 0.0) or 0.0), float(micro_volatility or 0.0) * 3.0, 0.001)
    max_loss_budget = account_equity * per_trade_risk_fraction
    stop_distance_abs = (last_price * stop_distance_fraction) if last_price else 0.0
    target_quantity_risk = (max_loss_budget / stop_distance_abs) if stop_distance_abs else 0.0
    target_notional_cap = min(account_equity * max_symbol_notional_fraction, cash_available)
    target_quantity_cap = (target_notional_cap / last_price) if last_price else 0.0
    target_quantity = min(target_quantity_risk, target_quantity_cap) if target_quantity_risk and target_quantity_cap else 0.0
    target_notional = target_quantity * last_price if last_price and target_quantity else 0.0

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

    entry_side = strategy_state.get('entry_side', 'long')
    stop_price = None
    if last_price:
        stop_price = last_price * (1 - stop_distance_fraction) if entry_side == 'long' else last_price * (1 + stop_distance_fraction)

    return {
        'symbol': symbol,
        'signal_name': strategy_name,
        'risk_status': risk_status,
        'allow_entry': allow_entry,
        'rejection_reasons': rejection_reasons,
        'advisory_flags': advisory_flags,
        'sizing_mode': 'risk_budget_capped_notional',
        'target_notional': round(float(target_notional), 8),
        'target_quantity': round(float(target_quantity), 8),
        'max_loss_budget': round(float(max_loss_budget), 8),
        'stop_policy': {
            'stop_policy_type': 'volatility_scaled_stop',
            'initial_stop_price': round(float(stop_price), 8) if stop_price else None,
            'stop_distance_fraction': round(float(stop_distance_fraction), 8),
            'stop_reason': 'default_v1_volatility_scaled',
            'trailing_policy': None,
        },
        'take_profit_policy': {
            'policy_type': 'fixed_rr_target',
            'rr_multiple': 2.0,
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
