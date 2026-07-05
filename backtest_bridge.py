from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime, UTC
from typing import Dict, Any, List

BASE = Path(__file__).resolve().parent
RK = BASE / 'research_knowledge'
RUNTIME = BASE / 'runtime'

DEFAULT_THRESHOLDS = {
    'strong': {'min_quality_score': 24, 'min_backtest_score': 24},
    'review': {'min_quality_score': 18, 'min_backtest_score': 18},
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load_expanded_strategy_catalog() -> Dict[str, Any]:
    return json.loads((RK / 'expanded_strategy_catalog_v1.json').read_text())


def load_validator_report() -> Dict[str, Any]:
    path = RUNTIME / 'research_validator_report.json'
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {'strategy_validation': {'rows': []}, 'signal_validation': {'rows': []}}


def _index_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {row['id']: row for row in rows}


def build_backtest_jobs() -> Dict[str, Any]:
    catalog = load_expanded_strategy_catalog()
    report = load_validator_report()
    strategy_rows = _index_rows(report.get('strategy_validation', {}).get('rows', []))
    signal_rows = _index_rows(report.get('signal_validation', {}).get('rows', []))

    jobs = []
    for family_id, item in catalog.get('strategy_families', {}).items():
        linked_signals = [signal_rows.get(sig, {'id': sig, 'decision': 'UNSCORED', 'scores': {'total': 0}}) for sig in item.get('source_signals', [])]
        strategy_row = strategy_rows.get(family_id, {'id': family_id, 'decision': 'UNSCORED', 'scores': {'total': 0}})
        job = {
            'job_id': f'bt_{family_id}',
            'created_at': _now(),
            'strategy_family': family_id,
            'source_signals': item.get('source_signals', []),
            'validation_focus': item.get('validation_focus', []),
            'risk_focus': item.get('risk_focus', []),
            'promotion_rule': item.get('promotion_rule'),
            'research_quality_score': strategy_row.get('scores', {}).get('total', 0),
            'upstream_signal_quality_min': min([row.get('scores', {}).get('total', 0) for row in linked_signals] or [0]),
            'upstream_signal_quality_avg': sum([row.get('scores', {}).get('total', 0) for row in linked_signals] or [0]) / max(len(linked_signals), 1),
            'research_decision': strategy_row.get('decision', 'UNSCORED'),
            'backtest_spec': {
                'engine_profile': 'baseline_v1',
                'slippage_model': 'default_placeholder',
                'fee_model': 'default_placeholder',
                'walkforward_required': True,
                'oos_required': True,
            },
            'status': 'queued_for_backtest'
        }
        jobs.append(job)
    return {'generated_at': _now(), 'job_count': len(jobs), 'jobs': jobs}


def score_backtest_result(result: Dict[str, Any]) -> Dict[str, Any]:
    pnl = result.get('pnl_score', 0)
    dd = result.get('drawdown_score', 0)
    stability = result.get('stability_score', 0)
    robustness = result.get('robustness_score', 0)
    execution = result.get('execution_score', 0)
    total = pnl + dd + stability + robustness + execution
    if total >= DEFAULT_THRESHOLDS['strong']['min_backtest_score']:
        decision = 'promote'
    elif total >= DEFAULT_THRESHOLDS['review']['min_backtest_score']:
        decision = 'qualify'
    elif total >= 12:
        decision = 'revise'
    else:
        decision = 'reject'
    return {'backtest_score_total': total, 'decision': decision}


def build_bridge_demo() -> Dict[str, Any]:
    jobs = build_backtest_jobs()['jobs']
    demo_results = []
    for job in jobs:
        rq = job['research_quality_score']
        simulated = {
            'job_id': job['job_id'],
            'pnl_score': min(5, max(2, rq // 5)),
            'drawdown_score': 4,
            'stability_score': 4 if job['upstream_signal_quality_avg'] >= 22 else 3,
            'robustness_score': 4 if job['upstream_signal_quality_min'] >= 20 else 3,
            'execution_score': 5 if 'execution' in job['strategy_family'] else 4,
        }
        demo_results.append({**job, 'simulated_backtest': simulated, 'decision_gate': score_backtest_result(simulated)})
    out = {'generated_at': _now(), 'job_count': len(demo_results), 'jobs': demo_results}
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / 'backtest_bridge_demo.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(json.dumps(build_bridge_demo(), ensure_ascii=False, indent=2))
