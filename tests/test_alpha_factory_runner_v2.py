import json
from pathlib import Path
from signal_generator import SignalGenerator
from alpha_factory_runner import AlphaFactoryRunner


def test_runner_builds_revalidation_tasks_after_decay_and_demotion(tmp_path):
    root = Path(__file__).resolve().parents[1]
    factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()[:2]
    runner = AlphaFactoryRunner(tmp_path / 'registry_store')
    alpha_defs = []
    for i, c in enumerate(candidates, start=1):
        alpha_defs.append({'alpha_id': f'alpha_{i}', 'alpha_name': c['signal_name'], 'source_type': 'generated', 'symbol_scope': 'BTC', 'universe_scope': 'crypto', 'timeframe': c['timeframe'], 'regime_scope': c['regime_scope'], 'factor_dependencies': c['source_expression_ids'], 'indicator_dependencies': [], 'signal_template_family': c['template_family'], 'signal_expression': c['trigger_definition'], 'parameter_set': c['parameter_set'], 'thesis_summary': c['thesis_summary'], 'lineage_parent_ids': [], 'created_by': 'system'})
    runner.register_alphas(alpha_defs)
    runner.run_validation(candidates, observations={
        candidates[0]['signal_candidate_id']: {'alpha_id': 'alpha_1', 'expectancy': 0.03, 'sharpe': 1.9, 'sortino': 2.3, 'drawdown_max': 0.08, 'turnover': 0.25, 'capacity_proxy': 0.7, 'win_rate': 0.56},
        candidates[1]['signal_candidate_id']: {'alpha_id': 'alpha_2', 'expectancy': -0.01, 'sharpe': 0.3, 'sortino': 0.2, 'drawdown_max': 0.15, 'turnover': 0.4, 'capacity_proxy': 0.6, 'win_rate': 0.45},
    })
    decisions = runner.run_promotion(current_states={'alpha_1': 'validated', 'alpha_2': 'validated'})
    runner.registry.add_validation_scorecard({'alpha_id': 'alpha_1', 'validation_run_id': 'run_later', 'research_score': 50, 'sharpe': 1.0, 'expectancy': 0.01})
    runner.run_decay_scan()
    tasks = runner.build_revalidation_tasks()
    assert any(d['target_state'] == 'demoted' for d in decisions)
    assert tasks
