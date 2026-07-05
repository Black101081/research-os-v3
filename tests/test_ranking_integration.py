import json
from pathlib import Path
from signal_generator import SignalGenerator
from alpha_factory_runner import AlphaFactoryRunner


def test_runner_validation_returns_ranked_scorecards(tmp_path):
    root = Path(__file__).resolve().parents[1]
    factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()[:2]
    runner = AlphaFactoryRunner(tmp_path / 'registry_store')
    runner.register_alphas([
        {'alpha_id': 'alpha_1', 'alpha_name': 'a1', 'source_type': 'generated', 'symbol_scope': 'BTC', 'universe_scope': 'crypto', 'timeframe': '1m', 'regime_scope': candidates[0]['regime_scope'], 'factor_dependencies': candidates[0]['source_expression_ids'], 'indicator_dependencies': [], 'signal_template_family': candidates[0]['template_family'], 'signal_expression': candidates[0]['trigger_definition'], 'parameter_set': candidates[0]['parameter_set'], 'thesis_summary': candidates[0]['thesis_summary'], 'lineage_parent_ids': [], 'created_by': 'system'},
        {'alpha_id': 'alpha_2', 'alpha_name': 'a2', 'source_type': 'generated', 'symbol_scope': 'BTC', 'universe_scope': 'crypto', 'timeframe': '1m', 'regime_scope': candidates[1]['regime_scope'], 'factor_dependencies': candidates[1]['source_expression_ids'], 'indicator_dependencies': [], 'signal_template_family': candidates[1]['template_family'], 'signal_expression': candidates[1]['trigger_definition'], 'parameter_set': candidates[1]['parameter_set'], 'thesis_summary': candidates[1]['thesis_summary'], 'lineage_parent_ids': [], 'created_by': 'system'}
    ])
    ranked = runner.run_validation(candidates, observations={
        candidates[0]['signal_candidate_id']: {'alpha_id': 'alpha_1', 'expectancy': 0.03, 'sharpe': 1.9, 'sortino': 2.3, 'drawdown_max': 0.08, 'turnover': 0.25, 'capacity_proxy': 0.7, 'win_rate': 0.56},
        candidates[1]['signal_candidate_id']: {'alpha_id': 'alpha_2', 'expectancy': 0.01, 'sharpe': 0.6, 'sortino': 0.7, 'drawdown_max': 0.12, 'turnover': 0.30, 'capacity_proxy': 0.7, 'win_rate': 0.51},
    })
    assert ranked[0]['research_rank'] == 1
    assert ranked[0]['research_score'] >= ranked[1]['research_score']
