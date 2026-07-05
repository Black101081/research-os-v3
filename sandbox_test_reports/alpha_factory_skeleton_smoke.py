import sys, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from signal_generator import SignalGenerator
from candidate_pruner import CandidatePruner
from ranking_engine import RankingEngine
from alpha_registry import AlphaRegistry

factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
sg = SignalGenerator(factor_catalog, template_library)
candidates = sg.generate_candidates()
kept, dropped = CandidatePruner().prune(candidates)
registry = AlphaRegistry()
for i, c in enumerate(kept[:3], start=1):
    registry.add_alpha_definition({
        'alpha_id': f'alpha_{i}',
        'alpha_name': c['signal_name'],
        'source_type': 'generated',
        'symbol_scope': 'BTC',
        'universe_scope': 'crypto',
        'timeframe': c['timeframe'],
        'regime_scope': c['regime_scope'],
        'factor_dependencies': c['source_expression_ids'],
        'indicator_dependencies': [],
        'signal_template_family': c['template_family'],
        'signal_expression': c['trigger_definition'],
        'parameter_set': c['parameter_set'],
        'thesis_summary': c['thesis_summary'],
        'lineage_parent_ids': [],
        'created_by': 'system',
    })
scorecards = [
    {'alpha_id': 'alpha_1', 'sharpe': 1.8, 'sortino': 2.2, 'expectancy': 0.02, 'drawdown_max': 0.08, 'turnover': 0.3, 'stability_score': 0.7, 'overfit_risk_score': 0.2},
    {'alpha_id': 'alpha_2', 'sharpe': 1.1, 'sortino': 1.4, 'expectancy': 0.01, 'drawdown_max': 0.05, 'turnover': 0.2, 'stability_score': 0.6, 'overfit_risk_score': 0.1},
]
ranked = RankingEngine().rank(scorecards)
print(json.dumps({
    'generated_candidates': len(candidates),
    'kept_candidates': len(kept),
    'dropped_candidates': len(dropped),
    'alpha_definitions': len(registry.alpha_definitions),
    'top_ranked_alpha': ranked[0]['alpha_id'] if ranked else None,
    'top_research_score': ranked[0]['research_score'] if ranked else None,
}, ensure_ascii=False))
