from promotion_engine import PromotionDemotionEngineV1


def test_promotion_engine_promotes_high_score_candidate():
    engine = PromotionDemotionEngineV1()
    alpha = {'alpha_id': 'alpha_1', 'alpha_name': 'sig_1'}
    scorecard = {'validation_run_id': 'run_1', 'research_score': 88, 'drawdown_max': 0.08, 'overfit_risk_score': 0.10, 'validation_status': 'accepted_for_ranking'}
    decision = engine.decide(alpha, scorecard, current_state='validated')
    assert decision['transition_allowed'] is True
    assert decision['target_state'] == 'promoted'
