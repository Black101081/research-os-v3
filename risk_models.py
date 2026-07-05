from __future__ import annotations

from copy import deepcopy

DEFAULT_RISK_CONFIG_V1 = {
    'account_equity': 100000.0,
    'cash_available': 100000.0,
    'per_trade_risk_fraction': 0.005,
    'max_symbol_notional_fraction': 0.10,
    'max_portfolio_gross_fraction': 0.50,
    'max_concurrent_candidates': 5,
    'session_loss_limit_fraction': 0.03,
    'spread_bps_limits': {
        'default': 12.0,
        'bollinger_squeeze_breakout': 8.0,
        'zscore_recenter': 15.0,
        'macd_trend_continuation': 10.0,
    },
    'micro_volatility_limits': {
        'default': 0.0030,
        'bollinger_squeeze_breakout': 0.0045,
        'zscore_recenter': 0.0060,
        'macd_trend_continuation': 0.0040,
    },
    'kill_switch': {
        'active': False,
        'scope': 'global',
        'trigger_reason': None,
        'triggered_at': None,
        'reset_condition': 'manual',
    },
    'portfolio_state': {
        'gross_exposure': 0.0,
        'net_exposure': 0.0,
        'active_positions_count': 0,
        'active_high_vol_positions_count': 0,
        'session_realized_pnl': 0.0,
        'symbol_exposure': {},
        'open_positions': {},
    },
}


def merge_risk_config(overrides: dict | None = None) -> dict:
    config = deepcopy(DEFAULT_RISK_CONFIG_V1)
    if not overrides:
        return config
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config
