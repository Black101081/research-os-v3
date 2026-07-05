from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime, UTC
from typing import Dict, Any

from backtest_bridge import build_bridge_demo, score_backtest_result

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _simulate_metrics(job: Dict[str, Any]) -> Dict[str, Any]:
    rq = int(job.get('research_quality_score', 0))
    avg_sig = float(job.get('upstream_signal_quality_avg', 0))
    min_sig = float(job.get('upstream_signal_quality_min', 0))
    trade_count = max(24, int(20 + avg_sig * 2))
    gross_pnl = round(0.8 * rq + 0.35 * avg_sig, 2)
    max_drawdown = round(max(4.0, 18.0 - (min_sig / 2.5)), 2)
    win_rate = round(min(0.74, 0.42 + avg_sig / 100), 3)
    expectancy = round((gross_pnl / trade_count) * (1 - max_drawdown / 100), 4)
    net_pnl = round(gross_pnl - max_drawdown * 0.55, 2)
    stability_score = 5 if avg_sig >= 23 else 4 if avg_sig >= 21 else 3
    robustness_score = 5 if min_sig >= 23 else 4 if min_sig >= 20 else 3
    execution_score = 5 if 'execution' in job.get('strategy_family', '') else 4
    return {
        'job_id': job['job_id'],
        'trade_count': trade_count,
        'gross_pnl': gross_pnl,
        'net_pnl': net_pnl,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'expectancy': expectancy,
        'stability_score': stability_score,
        'robustness_score': robustness_score,
        'execution_score': execution_score,
    }


def run_backtest_runner_demo() -> Dict[str, Any]:
    bridge = build_bridge_demo()
    results = []
    for job in bridge.get('jobs', []):
        metrics = _simulate_metrics(job)
        gate_inputs = {
            'pnl_score': min(5, max(2, int(metrics['net_pnl'] // 5) + 1)),
            'drawdown_score': 5 if metrics['max_drawdown'] <= 8 else 4 if metrics['max_drawdown'] <= 12 else 3,
            'stability_score': metrics['stability_score'],
            'robustness_score': metrics['robustness_score'],
            'execution_score': metrics['execution_score'],
        }
        gate = score_backtest_result(gate_inputs)
        notes = 'Execution-aware family' if 'execution' in job.get('strategy_family', '') else 'Baseline family'
        results.append({**job, 'runner_metrics': metrics, 'decision_gate': gate, 'notes': notes})
    out = {'generated_at': _now(), 'result_count': len(results), 'results': results}
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / 'backtest_runner_demo.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(json.dumps(run_backtest_runner_demo(), ensure_ascii=False, indent=2))
