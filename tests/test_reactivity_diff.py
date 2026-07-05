from __future__ import annotations

from reactivity_diff import build_reactivity_diff_v1


def test_reactivity_diff_reports_changed_fields():
    before = {
        'current_bar': {'close': 100},
        'factors': {'ret_1': 0.01},
        'indicators': {'MACD': 1.0},
        'regime_state': {'regime': 'uptrend'},
        'signals': {'sigA': {'active': False}},
        'strategies': {'sigA': {'execution_ready': False}},
        'risk_packets': {'sigA': {'risk_status': 'BLOCK'}},
        'validation_packet': {'decision_hint': 'standby'},
    }
    after = {
        'current_bar': {'close': 101},
        'factors': {'ret_1': 0.02, 'tick_ret_1': 0.001},
        'indicators': {'MACD': 1.5},
        'regime_state': {'regime': 'transition_ambiguous'},
        'signals': {'sigA': {'active': True}},
        'strategies': {'sigA': {'execution_ready': True}},
        'risk_packets': {'sigA': {'risk_status': 'ALLOW'}},
        'validation_packet': {'decision_hint': 'qualify'},
    }
    diff = build_reactivity_diff_v1('BTC', 'trades', before, after, reactive_source='live_intrabar')
    assert diff['current_bar_changed'] is True
    assert 'ret_1' in diff['factors_changed']
    assert 'tick_ret_1' in diff['factors_changed']
    assert 'MACD' in diff['indicators_changed']
    assert diff['regime_changed'] is True
    assert 'sigA' in diff['signals_changed']
    assert 'sigA' in diff['strategies_changed']
    assert diff['risk_changed'] is True
    assert diff['validation_changed'] is True
