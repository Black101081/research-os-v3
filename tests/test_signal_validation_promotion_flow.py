import json
from pathlib import Path
from signal_generator import SignalGenerator
from validation_runner import ValidationRunnerV1
from promotion_engine import PromotionDemotionEngineV1


def test_signal_validation_promotion_flow_runs_end_to_end():
    root = Path(__file__).resolve().parents[1]
    factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()
    runner = ValidationRunnerV1()
    scorecards = runner.validate_candidates(candidates)
    alpha_defs = []
    latest = {}
    for idx, row in enumerate(scorecards[:3], start=1):
        alpha_id = f'alpha_{idx}'
        row['alpha_id'] = alpha_id
        latest[alpha_id] = row
        alpha_defs.append({'alpha_id': alpha_id, 'alpha_name': row['candidate_id']})
    decisions = PromotionDemotionEngineV1().batch_decide(alpha_defs, latest, current_states={alpha['alpha_id']: 'validated' for alpha in alpha_defs})
    assert decisions
    assert all('target_state' in d for d in decisions)
