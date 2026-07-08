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
    'sizing_model': 'atr',
    'risk_pct_per_trade': 0.01,
    'atr_stop_multiplier': 1.5,
    'rr_ratio': 2.0,
    'min_quantity': 0.001,
    'max_quantity': 0.5,
    'max_position_pct': 0.10,
    'kelly_fraction': 0.25,
    'max_kelly_pct': 0.05,
    'min_trades_for_kelly': 10,
    'fixed_quantity': 0.01,
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


_default_config_cached: dict | None = None

def merge_risk_config(overrides: dict | None = None) -> dict:
    global _default_config_cached
    if not overrides:
        if _default_config_cached is None:
            _default_config_cached = {
                'account_equity': DEFAULT_RISK_CONFIG_V1['account_equity'],
                'cash_available': DEFAULT_RISK_CONFIG_V1['cash_available'],
                'per_trade_risk_fraction': DEFAULT_RISK_CONFIG_V1['per_trade_risk_fraction'],
                'max_symbol_notional_fraction': DEFAULT_RISK_CONFIG_V1['max_symbol_notional_fraction'],
                'max_portfolio_gross_fraction': DEFAULT_RISK_CONFIG_V1['max_portfolio_gross_fraction'],
                'max_concurrent_candidates': DEFAULT_RISK_CONFIG_V1['max_concurrent_candidates'],
                'session_loss_limit_fraction': DEFAULT_RISK_CONFIG_V1['session_loss_limit_fraction'],
                'sizing_model': DEFAULT_RISK_CONFIG_V1['sizing_model'],
                'risk_pct_per_trade': DEFAULT_RISK_CONFIG_V1['risk_pct_per_trade'],
                'atr_stop_multiplier': DEFAULT_RISK_CONFIG_V1['atr_stop_multiplier'],
                'rr_ratio': DEFAULT_RISK_CONFIG_V1['rr_ratio'],
                'min_quantity': DEFAULT_RISK_CONFIG_V1['min_quantity'],
                'max_quantity': DEFAULT_RISK_CONFIG_V1['max_quantity'],
                'max_position_pct': DEFAULT_RISK_CONFIG_V1['max_position_pct'],
                'kelly_fraction': DEFAULT_RISK_CONFIG_V1['kelly_fraction'],
                'max_kelly_pct': DEFAULT_RISK_CONFIG_V1['max_kelly_pct'],
                'min_trades_for_kelly': DEFAULT_RISK_CONFIG_V1['min_trades_for_kelly'],
                'fixed_quantity': DEFAULT_RISK_CONFIG_V1['fixed_quantity'],
                'spread_bps_limits': DEFAULT_RISK_CONFIG_V1['spread_bps_limits'].copy(),
                'micro_volatility_limits': DEFAULT_RISK_CONFIG_V1['micro_volatility_limits'].copy(),
                'kill_switch': DEFAULT_RISK_CONFIG_V1['kill_switch'].copy(),
                'portfolio_state': {
                    'gross_exposure': DEFAULT_RISK_CONFIG_V1['portfolio_state']['gross_exposure'],
                    'net_exposure': DEFAULT_RISK_CONFIG_V1['portfolio_state']['net_exposure'],
                    'active_positions_count': DEFAULT_RISK_CONFIG_V1['portfolio_state']['active_positions_count'],
                    'active_high_vol_positions_count': DEFAULT_RISK_CONFIG_V1['portfolio_state']['active_high_vol_positions_count'],
                    'session_realized_pnl': DEFAULT_RISK_CONFIG_V1['portfolio_state']['session_realized_pnl'],
                    'symbol_exposure': DEFAULT_RISK_CONFIG_V1['portfolio_state']['symbol_exposure'].copy(),
                    'open_positions': DEFAULT_RISK_CONFIG_V1['portfolio_state']['open_positions'].copy(),
                }
            }
        return _default_config_cached

    config = {
        'account_equity': DEFAULT_RISK_CONFIG_V1['account_equity'],
        'cash_available': DEFAULT_RISK_CONFIG_V1['cash_available'],
        'per_trade_risk_fraction': DEFAULT_RISK_CONFIG_V1['per_trade_risk_fraction'],
        'max_symbol_notional_fraction': DEFAULT_RISK_CONFIG_V1['max_symbol_notional_fraction'],
        'max_portfolio_gross_fraction': DEFAULT_RISK_CONFIG_V1['max_portfolio_gross_fraction'],
        'max_concurrent_candidates': DEFAULT_RISK_CONFIG_V1['max_concurrent_candidates'],
        'session_loss_limit_fraction': DEFAULT_RISK_CONFIG_V1['session_loss_limit_fraction'],
        'sizing_model': DEFAULT_RISK_CONFIG_V1['sizing_model'],
        'risk_pct_per_trade': DEFAULT_RISK_CONFIG_V1['risk_pct_per_trade'],
        'atr_stop_multiplier': DEFAULT_RISK_CONFIG_V1['atr_stop_multiplier'],
        'rr_ratio': DEFAULT_RISK_CONFIG_V1['rr_ratio'],
        'min_quantity': DEFAULT_RISK_CONFIG_V1['min_quantity'],
        'max_quantity': DEFAULT_RISK_CONFIG_V1['max_quantity'],
        'max_position_pct': DEFAULT_RISK_CONFIG_V1['max_position_pct'],
        'kelly_fraction': DEFAULT_RISK_CONFIG_V1['kelly_fraction'],
        'max_kelly_pct': DEFAULT_RISK_CONFIG_V1['max_kelly_pct'],
        'min_trades_for_kelly': DEFAULT_RISK_CONFIG_V1['min_trades_for_kelly'],
        'fixed_quantity': DEFAULT_RISK_CONFIG_V1['fixed_quantity'],
        'spread_bps_limits': DEFAULT_RISK_CONFIG_V1['spread_bps_limits'].copy(),
        'micro_volatility_limits': DEFAULT_RISK_CONFIG_V1['micro_volatility_limits'].copy(),
        'kill_switch': DEFAULT_RISK_CONFIG_V1['kill_switch'].copy(),
        'portfolio_state': {
            'gross_exposure': DEFAULT_RISK_CONFIG_V1['portfolio_state']['gross_exposure'],
            'net_exposure': DEFAULT_RISK_CONFIG_V1['portfolio_state']['net_exposure'],
            'active_positions_count': DEFAULT_RISK_CONFIG_V1['portfolio_state']['active_positions_count'],
            'active_high_vol_positions_count': DEFAULT_RISK_CONFIG_V1['portfolio_state']['active_high_vol_positions_count'],
            'session_realized_pnl': DEFAULT_RISK_CONFIG_V1['portfolio_state']['session_realized_pnl'],
            'symbol_exposure': DEFAULT_RISK_CONFIG_V1['portfolio_state']['symbol_exposure'].copy(),
            'open_positions': DEFAULT_RISK_CONFIG_V1['portfolio_state']['open_positions'].copy(),
        }
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config
