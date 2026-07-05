from __future__ import annotations

from realtime_engine import ResearchEngine


def test_integration_reactivity_and_risk_packets_flow_into_snapshot():
    engine = ResearchEngine(symbols=['BTC'], max_bars=500, thresholds={})
    for i in range(40):
        px = 60000 + i
        engine.process_message({'channel': 'candle', 'data': {'coin': 'BTC', 't': 1700000000000 + i * 60000, 'o': px - 1, 'h': px + 2, 'l': px - 2, 'c': px, 'v': 10 + i}})
    engine.process_message({'channel': 'bbo', 'data': {'coin': 'BTC', 'bid': 60039.5, 'ask': 60040.5}})
    engine.process_message({'channel': 'trades', 'data': [{'coin': 'BTC', 'px': 60045.0, 'sz': 0.25, 'side': 'B', 'time': 1700002405000}]})

    snap = engine.snapshot()['BTC']
    assert snap['risk_packets']
    assert snap['recent_reactivity']
    last_diff = snap['recent_reactivity'][-1]
    assert last_diff['message_type'] == 'trades'
    assert last_diff['risk_changed'] is True
    assert 'risk_statuses' in snap['validation_packet']
    assert any('risk_status' in v for v in snap['strategies'].values())
