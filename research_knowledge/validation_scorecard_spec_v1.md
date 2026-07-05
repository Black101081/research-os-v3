# Validation Scorecard Spec v1

Purpose: define a standardized scorecard for comparing alpha candidates across symbols, regimes, and windows.

## Required metrics
- expectancy
- sharpe
- sortino
- drawdown_max
- turnover
- capacity_proxy
- win_rate
- stability_score
- overfit_risk_score
- research_score

## Scoring principles
- raw return alone is never sufficient
- downside control matters
- regime consistency matters
- turnover and capacity penalize fragile alphas
- unstable candidates should be blocked or down-ranked

## Suggested v1 scoring formula
Research Score = Base Performance
- Fragility Penalty
- Overfit Penalty
- Turnover Penalty
+ Regime Robustness Bonus

Exact weights remain configurable.

## Validation statuses
- draft
- accepted_for_ranking
- revise
- reject
- quarantined

## Required outputs
Every validation run should emit:
- scorecard record
- regime panel records
- rejection reasons if any
- promotion recommendation
