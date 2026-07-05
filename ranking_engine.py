from __future__ import annotations

from typing import Any, Dict, List


def compute_research_score(scorecard: Dict[str, Any]) -> float:
    sharpe = float(scorecard.get('sharpe', 0.0) or 0.0)
    expectancy = float(scorecard.get('expectancy', 0.0) or 0.0)
    sortino = float(scorecard.get('sortino', 0.0) or 0.0)
    drawdown = abs(float(scorecard.get('drawdown_max', 0.0) or 0.0))
    turnover = float(scorecard.get('turnover', 0.0) or 0.0)
    stability = float(scorecard.get('stability_score', 0.0) or 0.0)
    overfit = float(scorecard.get('overfit_risk_score', 0.0) or 0.0)
    return round((sharpe * 25) + (sortino * 20) + (expectancy * 100) + (stability * 15) - (drawdown * 10) - (turnover * 5) - (overfit * 20), 4)


class RankingEngine:
    def rank(self, scorecards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked = []
        for row in scorecards:
            enriched = dict(row)
            enriched['research_score'] = compute_research_score(row)
            ranked.append(enriched)
        ranked.sort(key=lambda x: x.get('research_score', float('-inf')), reverse=True)
        for i, row in enumerate(ranked, start=1):
            row['research_rank'] = i
        return ranked
