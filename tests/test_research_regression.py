import json
import unittest
from pathlib import Path

from backtest_bridge import build_bridge_demo
from baseline_backtest_runner import run_backtest_runner_demo
from validator_runner import run_validator


class ResearchRegressionTests(unittest.TestCase):
    def test_validator_summary_contract(self):
        report = run_validator()
        summary = report['summary']
        for key in ['factor_count', 'indicator_count', 'signal_count', 'strategy_family_count']:
            self.assertIn(key, summary)
        self.assertEqual(summary['factor_count'], 100)
        self.assertEqual(summary['indicator_count'], 50)
        self.assertEqual(summary['signal_count'], 20)
        self.assertEqual(summary['strategy_family_count'], 8)

    def test_backtest_bridge_contract(self):
        data = build_bridge_demo()
        self.assertEqual(data['job_count'], 8)
        first = data['jobs'][0]
        for key in ['job_id', 'strategy_family', 'source_signals', 'validation_focus', 'risk_focus', 'promotion_rule', 'decision_gate']:
            self.assertIn(key, first)

    def test_backtest_runner_contract(self):
        data = run_backtest_runner_demo()
        self.assertEqual(data['result_count'], 8)
        first = data['results'][0]
        for key in ['job_id', 'runner_metrics', 'decision_gate', 'notes']:
            self.assertIn(key, first)
        for key in ['trade_count', 'gross_pnl', 'net_pnl', 'max_drawdown', 'win_rate', 'expectancy']:
            self.assertIn(key, first['runner_metrics'])


if __name__ == '__main__':
    unittest.main()
