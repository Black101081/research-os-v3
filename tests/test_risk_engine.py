from __future__ import annotations

from risk_engine import build_risk_packet_v1


def test_risk_engine_allows_candidate_with_normal_conditions():
    state = {
        'last_trade': 100.0,
        'last_price': 100.0,
        'regime_state': {'tradable': True, 'regime': 'uptrend'},
        'factors': {'trade_flow_imbalance_20': 0.1, 'micro_volatility_20': 0.001},
        'indicators': {'SpreadBps': 2.0, 'MicroVolatility': 0.001},
    }
    strategy = {'status': 'candidate', 'logic_ready': True, 'entry_side': 'long'}
    packet = build_risk_packet_v1('BTC', state, 'macd_trend_continuation', strategy)
    assert packet['allow_entry'] is True
    assert packet['risk_status'] in {'ALLOW', 'ALLOW_WITH_WARNINGS'}
    assert packet['target_quantity'] > 0


def test_risk_engine_blocks_when_spread_above_limit():
    state = {
        'last_trade': 100.0,
        'last_price': 100.0,
        'regime_state': {'tradable': True, 'regime': 'uptrend'},
        'factors': {'trade_flow_imbalance_20': 0.1, 'micro_volatility_20': 0.001},
        'indicators': {'SpreadBps': 50.0, 'MicroVolatility': 0.001},
    }
    strategy = {'status': 'candidate', 'logic_ready': True, 'entry_side': 'long'}
    packet = build_risk_packet_v1('BTC', state, 'macd_trend_continuation', strategy)
    assert packet['allow_entry'] is False
    assert packet['risk_status'] == 'BLOCK'
    assert 'spread_above_limit' in packet['rejection_reasons']


from risk_engine import compute_position_size

def test_position_sizing_atr_model():
    indicators = {'atr_pct_14': 0.02} # 2% ATR
    risk_config = {
        'sizing_model': 'atr',
        'risk_pct_per_trade': 0.01, # 1% risk
        'atr_stop_multiplier': 2.0, # 2x ATR stop distance = 4% stop
        'min_quantity': 0.001,
        'max_quantity': 50.0,
        'max_position_pct': 0.50,
        'account_equity': 10000.0
    }
    res = compute_position_size(
        symbol='BTC',
        last_price=100.0,
        indicators=indicators,
        risk_config=risk_config,
        portfolio_state={}
    )
    assert res['sizing_model_used'] == 'atr'
    assert res['target_quantity'] == 25.0
    assert res['stop_distance_usd'] == 4.0

def test_position_sizing_atr_bounds():
    indicators = {'atr_pct_14': 0.02}
    risk_config = {
        'sizing_model': 'atr',
        'risk_pct_per_trade': 0.01,
        'atr_stop_multiplier': 2.0,
        'min_quantity': 0.005,
        'max_quantity': 10.0,
        'max_position_pct': 0.05,
        'account_equity': 10000.0
    }
    res = compute_position_size(
        symbol='BTC',
        last_price=100.0,
        indicators=indicators,
        risk_config=risk_config,
        portfolio_state={}
    )
    assert res['target_quantity'] == 5.0

def test_position_sizing_kelly_model():
    risk_config = {
        'sizing_model': 'kelly',
        'kelly_fraction': 0.5,
        'max_kelly_pct': 0.08,
        'min_trades_for_kelly': 3,
        'max_quantity': 50.0,
        'account_equity': 10000.0
    }
    portfolio_state = {
        'trade_count': 5,
        'win_rate': 0.6,
        'avg_win_pct': 0.02,
        'avg_loss_pct': 0.01
    }
    res = compute_position_size(
        symbol='BTC',
        last_price=100.0,
        indicators={},
        risk_config=risk_config,
        portfolio_state=portfolio_state
    )
    assert res['sizing_model_used'] == 'kelly'
    assert res['kelly_f'] == 0.40
    assert res['target_quantity'] == 8.0

def test_position_sizing_kelly_fallback():
    indicators = {'atr_pct_14': 0.01}
    risk_config = {
        'sizing_model': 'kelly',
        'min_trades_for_kelly': 10,
        'risk_pct_per_trade': 0.02,
        'atr_stop_multiplier': 1.0,
        'max_quantity': 500.0,
        'account_equity': 10000.0
    }
    portfolio_state = {
        'trade_count': 2
    }
    res = compute_position_size(
        symbol='BTC',
        last_price=100.0,
        indicators=indicators,
        risk_config=risk_config,
        portfolio_state=portfolio_state
    )
    assert res['sizing_model_used'] == 'atr'
    assert 'Kelly fallback' in res['notes']

def test_position_sizing_fixed_model():
    risk_config = {
        'sizing_model': 'fixed',
        'fixed_quantity': 0.025
    }
    res = compute_position_size(
        symbol='BTC',
        last_price=100.0,
        indicators={},
        risk_config=risk_config,
        portfolio_state={}
    )
    assert res['sizing_model_used'] == 'fixed'
    assert res['target_quantity'] == 0.025

def test_position_sizing_edge_cases():
    risk_config = {'sizing_model': 'atr', 'fixed_quantity': 0.01}
    res = compute_position_size('BTC', 0.0, {'atr_pct_14': 0.02}, risk_config, {})
    assert res['sizing_model_used'] == 'fixed'
    assert res['target_quantity'] == 0.01

    res = compute_position_size('BTC', 100.0, {'atr_pct_14': 0.0}, risk_config, {})
    assert res['sizing_model_used'] == 'fixed'
    assert res['target_quantity'] == 0.01
