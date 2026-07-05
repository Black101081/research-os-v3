from __future__ import annotations

import math
from typing import Dict, Any, List

from realtime_engine import ResearchEngine
from strategy_spec_builder import build_strategy_spec_v1
from playbook_bridge import build_playbook_packet


def run_paper_replay_demo(config: Dict[str, Any], symbol: str = 'BTC') -> Dict[str, Any]:
    engine = ResearchEngine(symbols=[symbol], max_bars=500, thresholds=config['thresholds'])
    for i in range(60):
        base = 100 + i * 0.18 + math.sin(i / 8) * 0.03
        engine.process_message({'channel': 'candle', 'data': {'coin': symbol, 't': f'2026-07-05T01:{i:02d}:00Z', 'o': base - 0.05, 'h': base + 0.08, 'l': base - 0.08, 'c': base, 'v': 1000 + i * 2}})
    engine.process_message({'channel': 'trades', 'data': [{'coin': symbol, 'px': 110.81}]})
    engine.process_message({'channel': 'bbo', 'data': {'coin': symbol, 'bid': 110.80, 'ask': 110.82}})
    engine.process_message({'channel': 'allMids', 'data': {symbol: '110.81'}})
    snap = engine.snapshot()[symbol]
    specs: List[Dict[str, Any]] = []
    packets: List[Dict[str, Any]] = []
    for signal_name, signal_payload in snap['signals'].items():
        strategy = snap['strategies'].get(signal_name, {})
        if signal_payload.get('active') and strategy.get('execution_ready'):
            spec = build_strategy_spec_v1(symbol, signal_name, signal_payload, snap, config)
            packet = build_playbook_packet(spec)
            specs.append(spec)
            packets.append(packet)
    return {
        'symbol': symbol,
        'snapshot': snap,
        'strategy_specs': specs,
        'playbook_packets': packets,
    }
