# Strategy Thesis and Template Library

Purpose: define how a valid signal template is converted into a strategy object that can enter research, testing, qualification, and promotion workflows.

## Strategy conversion principles
- A signal is not yet a strategy.
- A strategy must add execution assumptions, risk assumptions, lifecycle stage, and testability constraints.
- Strategy templates should remain standardized so the playbook can compare candidates fairly.

## strategy_spec_v1
Required fields:
- spec_version
- spec_id
- created_at
- symbol
- signal_name
- signal_family
- thesis
- preferred_regimes
- avoid_regimes
- regime_at_creation
- market_data_context
- factor_snapshot
- indicator_snapshot
- entry_logic_source
- entry_side
- execution_assumptions
- risk_logic
- status
- next_stage

## Template philosophy by family

### Breakout strategy thesis
- Use when compression resolves into expansion with participation.
- Focus validation on slippage sensitivity, false breakout frequency, and post-breakout follow-through.
- Key risks: fakeouts, latency, thin order book conditions.

### Mean reversion strategy thesis
- Use when displacement is large but structural balance remains intact.
- Focus validation on adverse excursion, regime contamination, and persistence of stretch.
- Key risks: catching a real trend too early, volatility clustering.

### Trend continuation strategy thesis
- Use when trend is already established and momentum realigns.
- Focus validation on path dependency, pullback depth, and regime transitions.
- Key risks: late entries, exhaustion, whipsaw in transitions.

## Research lifecycle mapping
- Intake and hypothesis: spec created from live or replay signal.
- Spec lock: freeze hypothesis before heavy testing.
- Data and engine validation: verify bars, fees, slippage, symbol assumptions.
- Smoke test: check basic mechanics and no-lookahead assumptions.
- Baseline backtest: obtain first performance profile.
- Robustness and sensitivity: test parameters and execution assumptions.
- Out of sample and walk forward: test generalization.
- Decision gate: qualify, revise, reject, or promote.
- Portfolio promotion: integrate only after rule-based acceptance.
