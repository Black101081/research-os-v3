import sys, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from signal_generator import SignalGenerator
from alpha_factory_runner import AlphaFactoryRunner

factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()[:2]
runner = AlphaFactoryRunner(root / 'sandbox_test_reports' / 'alpha_registry_store_brief_demo')
alpha_defs = []
for i, c in enumerate(candidates, start=1):
    alpha_defs.append({'alpha_id': f'alpha_{i}', 'alpha_name': c['signal_name'], 'source_type': 'generated', 'symbol_scope': 'BTC', 'universe_scope': 'crypto', 'timeframe': c['timeframe'], 'regime_scope': c['regime_scope'], 'factor_dependencies': c['source_expression_ids'], 'indicator_dependencies': [], 'signal_template_family': c['template_family'], 'signal_expression': c['trigger_definition'], 'parameter_set': c['parameter_set'], 'thesis_summary': c['thesis_summary'], 'lineage_parent_ids': [], 'created_by': 'system'})
runner.register_alphas(alpha_defs)
runner.run_real_validation(candidates)
runner.run_promotion(current_states={'alpha_1': 'validated', 'alpha_2': 'validated'})
runner.registry.add_validation_scorecard({'alpha_id': 'alpha_1', 'validation_run_id': 'run_later', 'research_score': 40, 'sharpe': 0.9, 'expectancy': 0.005})
runner.run_decay_scan()
runner.build_revalidation_tasks()
paths = runner.generate_research_brief('brief_demo')
payload = json.loads(Path(paths['json_path']).read_text(encoding='utf-8'))
print(json.dumps({'json_path': paths['json_path'], 'md_path': paths['md_path'], 'top_ranked_count': len(payload['top_ranked_alphas']), 'promoted_count': payload['promoted_count'], 'decay_flag_count': payload['decay_flag_count'], 'revalidation_task_count': payload['revalidation_task_count']}, ensure_ascii=False))
