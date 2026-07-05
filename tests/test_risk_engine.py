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
