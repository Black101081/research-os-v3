from __future__ import annotations

from datetime import datetime, UTC
from typing import Dict, Any

PLAYBOOK_STAGES = [
    'intake_and_hypothesis',
    'spec_lock',
    'data_and_engine_validation',
    'smoke_test',
    'baseline_backtest',
    'robustness_and_sensitivity',
    'out_of_sample_and_walk_forward',
    'decision_gate',
    'portfolio_promotion',
]


def build_playbook_packet(strategy_spec: Dict[str, Any]) -> Dict[str, Any]:
    packet = {
        'packet_version': 'playbook_bridge_v1',
        'created_at': datetime.now(UTC).isoformat(),
        'spec_id': strategy_spec.get('spec_id'),
        'signal_name': strategy_spec.get('signal_name'),
        'symbol': strategy_spec.get('symbol'),
        'current_stage': 'intake_and_hypothesis',
        'allowed_next_stage': 'spec_lock',
        'research_status': 'pending_review',
        'decision_state': 'unreviewed',
        'stage_checklist': {
            'intake_and_hypothesis': 'pending',
            'spec_lock': 'blocked_until_review',
            'data_and_engine_validation': 'blocked_until_review',
            'smoke_test': 'blocked_until_review',
            'baseline_backtest': 'blocked_until_review',
            'robustness_and_sensitivity': 'blocked_until_review',
            'out_of_sample_and_walk_forward': 'blocked_until_review',
            'decision_gate': 'blocked_until_review',
            'portfolio_promotion': 'blocked_until_review',
        },
        'strategy_spec': strategy_spec,
    }
    return packet
