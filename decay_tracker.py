from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecayTrackerV1:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {
            'score_drop_threshold': 15.0,
            'sharpe_drop_threshold': 0.50,
            'expectancy_drop_threshold': 0.01,
        }

    def evaluate(self, alpha_id: str, historical_scorecards: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        if len(historical_scorecards) < 2:
            return None
        prior = historical_scorecards[-2]
        current = historical_scorecards[-1]
        prior_score = float(prior.get('research_score', 0.0) or 0.0)
        current_score = float(current.get('research_score', 0.0) or 0.0)
        prior_sharpe = float(prior.get('sharpe', 0.0) or 0.0)
        current_sharpe = float(current.get('sharpe', 0.0) or 0.0)
        prior_expectancy = float(prior.get('expectancy', 0.0) or 0.0)
        current_expectancy = float(current.get('expectancy', 0.0) or 0.0)
        decay_reasons = []
        if prior_score - current_score >= self.config['score_drop_threshold']:
            decay_reasons.append('research_score_drop')
        if prior_sharpe - current_sharpe >= self.config['sharpe_drop_threshold']:
            decay_reasons.append('sharpe_drop')
        if prior_expectancy - current_expectancy >= self.config['expectancy_drop_threshold']:
            decay_reasons.append('expectancy_drop')
        return {
            'alpha_id': alpha_id,
            'observation_window': f"{prior.get('validation_run_id')}->{current.get('validation_run_id')}",
            'prior_research_score': prior_score,
            'current_research_score': current_score,
            'delta_score': current_score - prior_score,
            'prior_sharpe': prior_sharpe,
            'current_sharpe': current_sharpe,
            'prior_expectancy': prior_expectancy,
            'current_expectancy': current_expectancy,
            'decay_flag': bool(decay_reasons),
            'decay_reason': ','.join(decay_reasons) if decay_reasons else None,
            'created_at': now_iso(),
        }
