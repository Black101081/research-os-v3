import sys, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from signal_generator import SignalGenerator
from validation_runner import ValidationRunnerV1
from promotion_engine import PromotionDemotionEngineV1

factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()
obs = {
    candidates[0]['signal_candidate_id']: {'expectancy': 0.03, 'sharpe': 1.9, 'sortino': 2.3, 'drawdown_max': 0.08, 'turnover': 0.25, 'capacity_proxy': 0.7, 'win_rate': 0.56},
    candidates[1]['signal_candidate_id']: {'expectancy': -0.01, 'sharpe': 0.3, 'sortino': 0.2, 'drawdown_max': 0.15, 'turnover': 0.4, 'capacity_proxy': 0.6, 'win_rate': 0.45},
}
scorecards = ValidationRunnerV1().validate_candidates(candidates[:2], observations=obs)
alpha_defs = []
latest = {}
for i, row in enumerate(scorecards, start=1):
    alpha_id = f'alpha_{i}'
    row['alpha_id'] = alpha_id
    latest[alpha_id] = row
    alpha_defs.append({'alpha_id': alpha_id, 'alpha_name': row['candidate_id']})
decisions = PromotionDemotionEngineV1().batch_decide(alpha_defs, latest, current_states={a['alpha_id']: 'validated' for a in alpha_defs})
print(json.dumps({'scorecards': scorecards, 'decisions': decisions}, ensure_ascii=False))
