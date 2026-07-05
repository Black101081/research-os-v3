# Backtest Runner Contract v1

Purpose: define the handoff between research strategy families and a baseline backtest engine interface.

## Runner input contract
Each runner job should include:
- job_id
- strategy_family
- source_signals
- validation_focus
- risk_focus
- promotion_rule
- research_quality_score
- upstream_signal_quality_min
- upstream_signal_quality_avg
- engine_profile
- slippage_model
- fee_model
- walkforward_required
- oos_required

## Runner output contract
Each runner result should include:
- job_id
- trade_count
- gross_pnl
- net_pnl
- max_drawdown
- win_rate
- expectancy
- stability_score
- robustness_score
- execution_score
- backtest_score_total
- decision
- notes

## Decision semantics
- promote: strong research quality plus strong backtest quality
- qualify: usable candidate ready for deeper review
- revise: structurally interesting but not yet robust enough
- reject: poor empirical quality or failed execution assumptions
