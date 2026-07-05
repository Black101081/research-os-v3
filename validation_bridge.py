from __future__ import annotations

from typing import Any, Dict


def build_validation_packet(symbol: str, state: Dict[str, Any]) -> Dict[str, Any]:
    active = [name for name, sig in state.get('signals', {}).items() if sig.get('active')]
    ready = [name for name, st in state.get('strategies', {}).items() if st.get('execution_ready')]
    regime_state = state.get('regime_state', {})
    risk_packets = state.get('risk_packets', {}) or {}
    risk_statuses = {name: packet.get('risk_status') for name, packet in risk_packets.items()}
    blocked = {name: packet.get('rejection_reasons', []) for name, packet in risk_packets.items() if packet.get('risk_status') in {'BLOCK', 'FLATTEN_ONLY'}}
    allow_count = sum(1 for packet in risk_packets.values() if packet.get('risk_status') == 'ALLOW')
    warn_count = sum(1 for packet in risk_packets.values() if packet.get('risk_status') == 'ALLOW_WITH_WARNINGS')
    block_count = sum(1 for packet in risk_packets.values() if packet.get('risk_status') in {'BLOCK', 'FLATTEN_ONLY'})

    decision_hint = 'qualify' if ready else ('revise' if active else 'standby')
    next_action = 'send_to_playbook' if ready else ('inspect_signal_logic' if active else 'wait_for_alignment')
    if block_count and not ready:
        decision_hint = 'risk_blocked'
        next_action = 'inspect_risk_rejections'

    packet = {
        'symbol': symbol,
        'regime': regime_state.get('regime'),
        'regime_confidence': regime_state.get('confidence'),
        'tradable': regime_state.get('tradable'),
        'active_signals': active,
        'execution_ready_strategies': ready,
        'risk_statuses': risk_statuses,
        'risk_summary': {
            'allow_count': allow_count,
            'allow_with_warnings_count': warn_count,
            'block_count': block_count,
            'blocked_reasons': blocked,
        },
        'decision_hint': decision_hint,
        'next_action': next_action,
    }
    return packet
