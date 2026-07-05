from ranking_engine import RankingEngine


def test_ranking_engine_sorts_highest_score_first():
    ranked = RankingEngine().rank([
        {'alpha_id': 'a1', 'sharpe': 1.0, 'sortino': 1.0, 'expectancy': 0.01, 'drawdown_max': 0.10, 'turnover': 0.4, 'stability_score': 0.5, 'overfit_risk_score': 0.3},
        {'alpha_id': 'a2', 'sharpe': 2.0, 'sortino': 2.0, 'expectancy': 0.02, 'drawdown_max': 0.05, 'turnover': 0.2, 'stability_score': 0.8, 'overfit_risk_score': 0.1},
    ])
    assert ranked[0]['alpha_id'] == 'a2'
    assert ranked[0]['research_score'] >= ranked[1]['research_score']
