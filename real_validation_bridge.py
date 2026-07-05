from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from baseline_backtest_runner import run_backtest_runner_demo


class RealValidationBridgeV1:
    def __init__(self, base: str | Path | None = None):
        self.base = Path(base) if base else Path(__file__).resolve().parent
        self.runtime = self.base / 'runtime'
        self.reports = self.base / 'sandbox_test_reports'

    def load_backtest_results(self) -> List[Dict[str, Any]]:
        path = self.runtime / 'backtest_runner_demo.json'
        if not path.exists():
            run_backtest_runner_demo()
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload.get('results', [])

    def load_live_soak_context(self) -> Dict[str, Any]:
        path = self.reports / 'btc_15m_soak_final.json'
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding='utf-8'))

    def _map_result_to_observation(self, alpha_id: str, result: Dict[str, Any], soak: Dict[str, Any]) -> Dict[str, Any]:
        metrics = result.get('runner_metrics', {})
        trade_count = float(metrics.get('trade_count', 0) or 0)
        max_drawdown = float(metrics.get('max_drawdown', 0) or 0)
        net_pnl = float(metrics.get('net_pnl', 0) or 0)
        expectancy = float(metrics.get('expectancy', 0) or 0)
        stability = float(metrics.get('stability_score', 0) or 0) / 5.0
        robustness = float(metrics.get('robustness_score', 0) or 0) / 5.0
        tradable = soak.get('tradable')
        risk_statuses = soak.get('risk_statuses', {}) or {}
        blocked = sum(1 for status in risk_statuses.values() if status == 'BLOCK')
        overfit = 0.30 if trade_count < 30 else 0.10
        if tradable is False and blocked:
            overfit = min(1.0, overfit + 0.05)
        sharpe = 0.0
        if max_drawdown > 0:
            sharpe = max(0.0, min(3.0, (net_pnl / max_drawdown) * 0.6))
        sortino = sharpe + 0.25
        fire_rate = min(0.80, trade_count / 100.0)
        capacity_proxy = min(1.0, max(0.1, trade_count / 120.0))
        turnover = 0.25 if trade_count >= 40 else 0.45
        return {
            'alpha_id': alpha_id,
            'sample_window': result.get('job_id'),
            'test_window': 'backtest_runner_demo',
            'expectancy': expectancy,
            'sharpe': round(sharpe, 4),
            'sortino': round(sortino, 4),
            'drawdown_max': round(max_drawdown / 100.0, 4),
            'turnover': turnover,
            'capacity_proxy': round(capacity_proxy, 4),
            'win_rate': float(metrics.get('win_rate', 0.5) or 0.5),
            'stability_score': round((stability + robustness) / 2.0, 4),
            'overfit_risk_score': round(overfit, 4),
            'fire_rate': round(fire_rate, 4),
            'profit_factor': round(max(0.5, 1.0 + expectancy * 10), 4),
            'live_context': {
                'tradable': tradable,
                'regime': soak.get('regime'),
                'risk_statuses': risk_statuses,
            },
        }

    def build_observations(self, alpha_definitions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        results = self.load_backtest_results()
        soak = self.load_live_soak_context()
        observations: Dict[str, Dict[str, Any]] = {}
        for alpha, result in zip(alpha_definitions, results):
            observations[alpha['alpha_id']] = self._map_result_to_observation(alpha['alpha_id'], result, soak)
        return observations
