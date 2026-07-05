import json
from pathlib import Path
from signal_generator import SignalGenerator
from alpha_factory_runner import AlphaFactoryRunner


def test_runner_real_validation_uses_bridge_runtime_inputs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()[:2]
    runner = AlphaFactoryRunner(tmp_path / 'registry_store')
    alpha_defs = []
    for i, c in enumerate(candidates, start=1):
        alpha_defs.append({'alpha_id': f'alpha_{i}', 'alpha_name': c['signal_name'], 'source_type': 'generated', 'symbol_scope': 'BTC', 'universe_scope': 'crypto', 'timeframe': c['timeframe'], 'regime_scope': c['regime_scope'], 'factor_dependencies': c['source_expression_ids'], 'indicator_dependencies': [], 'signal_template_family': c['template_family'], 'signal_expression': c['trigger_definition'], 'parameter_set': c['parameter_set'], 'thesis_summary': c['thesis_summary'], 'lineage_parent_ids': [], 'created_by': 'system'})
    runner.register_alphas(alpha_defs)
    ranked = runner.run_real_validation(candidates)
    assert ranked
    assert all('research_rank' in row for row in ranked)
    assert all(row['sample_window'] for row in ranked)
