from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ranking_engine import compute_research_score


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class ValidationRunnerV1:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def build_regime_panels(self, scorecard: Dict[str, Any], candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
        regimes = candidate.get('regime_scope') or ['unscoped']
        panels = []
        for regime in regimes:
            panels.append({
                'alpha_id': scorecard['alpha_id'],
                'regime_name': regime,
                'trade_count': int(max(1, round(scorecard.get('win_rate', 0.5) * 100))),
                'expectancy': scorecard.get('expectancy'),
                'sharpe': scorecard.get('sharpe'),
                'drawdown_max': scorecard.get('drawdown_max'),
                'turnover': scorecard.get('turnover'),
                'hit_rate': scorecard.get('win_rate'),
                'robustness_score': scorecard.get('stability_score'),
                'created_at': scorecard.get('created_at'),
            })
        return panels

    def validate_candidates(self, signal_candidates: List[Dict[str, Any]], observations: Dict[str, Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        observations = observations or {}
        scorecards: List[Dict[str, Any]] = []
        for idx, candidate in enumerate(signal_candidates):
            cid = candidate.get('signal_candidate_id', f'candidate_{idx}')
            obs = observations.get(cid, {})
            fire_rate = float(obs.get('fire_rate', 0.05) or 0.0)
            expectancy = float(obs.get('expectancy', 0.01) or 0.0)
            sharpe = float(obs.get('sharpe', 1.0) or 0.0)
            sortino = float(obs.get('sortino', sharpe + 0.2) or 0.0)
            drawdown = float(obs.get('drawdown_max', 0.08) or 0.0)
            turnover = float(obs.get('turnover', 0.20) or 0.0)
            capacity = float(obs.get('capacity_proxy', 0.60) or 0.0)
            win_rate = float(obs.get('win_rate', 0.52) or 0.0)
            stability = float(obs.get('stability_score', max(0.0, 1.0 - drawdown - turnover / 2.0)) or 0.0)
            overfit = float(obs.get('overfit_risk_score', 0.15 if fire_rate < 0.01 else 0.10) or 0.0)
            rejection_reasons = []
            if fire_rate <= 0.0:
                rejection_reasons.append('never_fires')
            if fire_rate > 0.80:
                rejection_reasons.append('fires_too_often')
            if turnover > 1.5:
                rejection_reasons.append('turnover_too_high')
            if drawdown > 0.30:
                rejection_reasons.append('drawdown_too_high')
            if capacity < 0.10:
                rejection_reasons.append('capacity_too_low')
            if expectancy <= 0:
                rejection_reasons.append('non_positive_expectancy')
            base = {
                'alpha_id': obs.get('alpha_id', cid),
                'validation_run_id': f'validation_{idx}_{int(datetime.now(timezone.utc).timestamp())}',
                'sample_window': obs.get('sample_window', 'sample_v1'),
                'train_window': obs.get('train_window'),
                'test_window': obs.get('test_window', 'test_v1'),
                'walk_forward_slice_id': obs.get('walk_forward_slice_id'),
                'expectancy': expectancy,
                'sharpe': sharpe,
                'sortino': sortino,
                'drawdown_max': drawdown,
                'turnover': turnover,
                'capacity_proxy': capacity,
                'win_rate': win_rate,
                'profit_factor': obs.get('profit_factor'),
                'stability_score': _bounded(stability, 0.0, 1.0),
                'overfit_risk_score': _bounded(overfit, 0.0, 1.0),
                'validation_status': 'accepted_for_ranking',
                'rejection_reasons': rejection_reasons,
                'created_at': now_iso(),
                'candidate_id': cid,
                'template_family': candidate.get('template_family'),
                'trigger_definition': candidate.get('trigger_definition'),
            }
            research_score = compute_research_score(base)
            base['research_score'] = research_score
            if rejection_reasons:
                base['validation_status'] = 'reject' if any(r in rejection_reasons for r in ['never_fires', 'turnover_too_high', 'drawdown_too_high', 'capacity_too_low', 'non_positive_expectancy']) else 'revise'
            elif research_score < 40:
                base['validation_status'] = 'revise'
            base['regime_panels'] = self.build_regime_panels(base, candidate)
            scorecards.append(base)
        return scorecards
