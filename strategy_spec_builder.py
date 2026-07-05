from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict


def build_strategy_spec_v1(symbol: str, signal_name: str, signal_payload: Dict[str, Any], state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    regime_state = state.get('regime_state', {})
    factors = state.get('factors', {})
    indicators = state.get('indicators', {})
    risk_packet = (state.get('risk_packets', {}) or {}).get(signal_name, {})
    strategy_state = (state.get('strategies', {}) or {}).get(signal_name, {})
    created_at = datetime.now(UTC).isoformat()
    spec_id_ts = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
    strategy_spec = {
        'spec_version': 'strategy_spec_v1',
        'spec_id': f'{signal_name}-{symbol}-{spec_id_ts}',
        'created_at': created_at,
        'symbol': symbol,
        'signal_name': signal_name,
        'signal_family': signal_payload.get('template_family'),
        'thesis': signal_payload.get('thesis'),
        'preferred_regimes': signal_payload.get('preferred_regimes', []),
        'avoid_regimes': signal_payload.get('avoid_regimes', []),
        'regime_at_creation': regime_state,
        'market_data_context': {
            'last_trade': state.get('last_trade'),
            'mid': state.get('mid'),
            'bars_loaded': len(state.get('bars', [])),
            'current_bar': state.get('current_bar'),
        },
        'factor_snapshot': factors,
        'indicator_snapshot': indicators,
        'entry_logic_source': signal_payload.get('why', {}),
        'entry_side': strategy_state.get('entry_side', 'long'),
        'execution_assumptions': {
            'network': config.get('network'),
            'candle_interval': config.get('candle_interval'),
            'fees_bps': config.get('execution', {}).get('fees_bps', 5),
            'slippage_bps': config.get('execution', {}).get('slippage_bps', 3),
        },
        'risk_logic': {
            'sizing_mode': risk_packet.get('sizing_mode', config.get('execution', {}).get('sizing_mode', 'fixed_fraction')),
            'max_fraction_per_trade': config.get('execution', {}).get('max_fraction_per_trade', 0.02),
            'kill_switch': 'disable if regime becomes non-tradable or signal invalidates',
        },
        'risk_snapshot': {
            'risk_status': risk_packet.get('risk_status'),
            'allow_entry': risk_packet.get('allow_entry'),
            'rejection_reasons': risk_packet.get('rejection_reasons', []),
            'advisory_flags': risk_packet.get('advisory_flags', []),
        },
        'status': strategy_state.get('status', 'candidate'),
        'next_stage': 'spec_lock',
    }
    return strategy_spec
