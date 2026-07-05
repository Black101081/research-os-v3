from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from alpha_lifecycle import AlphaLifecycleStateMachine


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PromotionDemotionEngineV1:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {
            'promote_score_min': 70.0,
            'shadow_score_min': 55.0,
            'demote_score_max': 35.0,
            'quarantine_drawdown_max': 0.25,
            'quarantine_overfit_max': 0.60,
        }
        self.lifecycle = AlphaLifecycleStateMachine()

    def decide(self, alpha_definition: Dict[str, Any], latest_scorecard: Dict[str, Any], current_state: str = 'validated') -> Dict[str, Any]:
        score = float(latest_scorecard.get('research_score', 0.0) or 0.0)
        drawdown = float(latest_scorecard.get('drawdown_max', 0.0) or 0.0)
        overfit = float(latest_scorecard.get('overfit_risk_score', 0.0) or 0.0)
        validation_status = latest_scorecard.get('validation_status')
        target_state = current_state
        trigger_reason = 'hold'

        if validation_status == 'reject' or score <= self.config['demote_score_max']:
            target_state = 'demoted'
            trigger_reason = 'low_research_score_or_rejected_validation'
        elif drawdown >= self.config['quarantine_drawdown_max'] or overfit >= self.config['quarantine_overfit_max']:
            target_state = 'quarantined'
            trigger_reason = 'risk_or_overfit_quarantine'
        elif score >= self.config['promote_score_min']:
            target_state = 'promoted'
            trigger_reason = 'promotion_threshold_met'
        elif score >= self.config['shadow_score_min']:
            target_state = 'shadow'
            trigger_reason = 'shadow_threshold_met'

        transition = self.lifecycle.transition(alpha_definition['alpha_id'], current_state, target_state, trigger_reason)
        return {
            'alpha_id': alpha_definition['alpha_id'],
            'alpha_name': alpha_definition.get('alpha_name'),
            'current_state': current_state,
            'target_state': transition.new_state,
            'transition_allowed': transition.allowed,
            'trigger_reason': transition.reason,
            'supporting_validation_run_id': latest_scorecard.get('validation_run_id'),
            'research_score': score,
            'created_at': now_iso(),
        }

    def batch_decide(self, alpha_definitions: List[Dict[str, Any]], latest_scorecards: Dict[str, Dict[str, Any]], current_states: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
        current_states = current_states or {}
        decisions = []
        for alpha in alpha_definitions:
            alpha_id = alpha['alpha_id']
            scorecard = latest_scorecards.get(alpha_id)
            if not scorecard:
                continue
            decisions.append(self.decide(alpha, scorecard, current_state=current_states.get(alpha_id, 'validated')))
        return decisions
