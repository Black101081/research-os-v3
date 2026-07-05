# Risk Engine v1 Spec

Purpose: define the first real risk layer for Research OS V3 so no signal or strategy can move toward execution without passing explicit capital, exposure, and failure controls.

## Position in pipeline
Market Data
-> OHLCV / Live Bars
-> Factors
-> Indicators
-> Regime
-> Signals
-> Strategies
-> Risk Engine
-> Validation
-> Playbook / Candidate Promotion

Risk Engine v1 is downstream of strategy formation but upstream of validation decisioning and playbook emission.

## Core principle
Signal quality is not permission to trade.
A strategy candidate becomes executable only when risk state, position state, and market state all permit it.

## Objectives
- Prevent oversized or fragile entries.
- Prevent multiple signals from creating hidden aggregate risk.
- Prevent execution under degraded liquidity or unstable conditions.
- Produce deterministic, inspectable risk decisions.
- Keep runtime and backtest semantics aligned.

## Scope of v1
Included:
- position sizing policy
- exposure limits
- stop framework contract
- tradability vetoes
- risk decision packet
- kill switch conditions
- integration hooks for runtime and backtest bridge

Deferred:
- portfolio optimizer
- correlation matrix engine
- volatility targeting across many symbols
- advanced liquidation path simulation
- broker/exchange-specific margin engine

## Risk inputs
The risk engine consumes:
- strategy object
- signal state
- regime state
- factor snapshot
- indicator snapshot
- live execution context
- current position state
- portfolio state summary

Minimum input contract:
- symbol
- entry_side
- strategy_family
- preferred_regime
- current_regime
- tradable
- confidence if available
- last_price
- spread_bps if available
- trade_flow_imbalance if available
- micro_volatility if available
- account_equity
- open_positions
- symbol_exposure
- portfolio_gross_exposure

## Risk outputs
Risk Engine v1 returns a `risk_packet_v1`.

Required fields:
- symbol
- strategy_id or signal_name
- risk_status
- allow_entry
- rejection_reasons
- advisory_flags
- sizing_mode
- target_notional
- target_quantity
- max_loss_budget
- stop_policy
- take_profit_policy
- kill_switch_state
- exposure_snapshot
- execution_constraints
- updated_at

Valid `risk_status` values:
- ALLOW
- ALLOW_WITH_WARNINGS
- BLOCK
- FLATTEN_ONLY

## Decision model
A strategy is executable only if all layers pass:
1. strategy active
2. regime tradable
3. signal not vetoed
4. risk engine allow_entry true
5. validation state not blocked

This means risk is a hard gate, not a descriptive annotation.

## Position sizing v1
Use a deterministic sizing ladder.

### Inputs
- account_equity
- per_trade_risk_fraction
- max_symbol_notional_fraction
- max_portfolio_gross_fraction
- stop_distance_fraction or fallback proxy
- confidence_bucket if available

### Sizing logic
Base loss budget:
- `max_loss_budget = account_equity * per_trade_risk_fraction`

Target quantity:
- if stop distance exists, quantity = max_loss_budget / stop_distance
- else fall back to capped notional sizing with warning

Apply caps:
- cap by symbol notional fraction
- cap by portfolio gross exposure fraction
- cap by exchange minimum increment rules when available

### Confidence shaping
Optional v1 shaping:
- low confidence -> 0.5x base size
- normal confidence -> 1.0x base size
- high confidence -> 1.25x base size, still capped by hard limits

## Exposure controls v1
### Symbol level
- max one directional position per symbol per strategy family unless explicitly allowed
- max symbol notional fraction
- no add-to-loser behavior in v1

### Portfolio level
- max gross exposure fraction
- max concurrent active candidates
- max simultaneous high-volatility positions

### Strategy family level
- block duplicate entries from overlapping breakout or mean-reversion families on the same symbol
- require explicit merge rule when multiple signals map to one strategy family

## Stop framework v1
Stop framework is mandatory for ALLOW state.

Allowed stop policies:
- fixed_fraction_stop
- structure_stop
- volatility_scaled_stop
- microstructure_abort

Required stop fields:
- stop_policy_type
- initial_stop_price or invalidation_level
- stop_distance_fraction
- stop_reason
- trailing_policy optional

Rules:
- missing stop definition downgrades to BLOCK unless strategy is explicitly non-executable research-only
- stop distance too tight relative to spread/micro volatility triggers warning or block
- stop distance too wide relative to loss budget forces size reduction

## Take profit framework v1
Take profit is optional, but if defined must be explicit.

Allowed policies:
- fixed_rr_target
- structure_target
- partial_scaleout
- open_ended_with_trailing_stop

v1 requirement:
- every strategy must specify whether it is fixed-target or open-ended

## Tradability vetoes
Entry is blocked if any of the following are true:
- regime not tradable
- spread_bps above threshold
- micro_volatility above threshold for the strategy family
- trade_flow_imbalance contradicts the entry beyond threshold if configured
- symbol already has blocked or conflicting exposure
- kill switch active

These vetoes must be recorded in `rejection_reasons`.

## Kill switch v1
Kill switch operates at runtime and can force `FLATTEN_ONLY` or `BLOCK`.

Trigger examples:
- repeated parser/schema failures
- repeated websocket disconnects
- stale market data
- repeated risk packet construction failures
- realized loss threshold for session exceeded
- slippage anomaly threshold exceeded

Kill switch state fields:
- active
- scope: symbol / strategy_family / global
- trigger_reason
- triggered_at
- reset_condition

## Runtime state contracts
### Position state v1
- symbol
- side
- quantity
- avg_entry_price
- unrealized_pnl
- realized_pnl_session
- stop_price
- opened_at
- strategy_family

### Portfolio summary v1
- account_equity
- cash_available
- gross_exposure
- net_exposure
- active_positions_count
- active_high_vol_positions_count
- session_realized_pnl

## Integration points
### Realtime engine integration
After strategies are built:
- compute risk packet
- attach `risk_packet_v1` to symbol state
- only mark `execution_ready` true when risk packet allows entry

### Validation bridge integration
Validation should consume risk packet and include:
- risk_status
- allow_entry
- rejection_reasons
- sizing summary
- stop summary

### Backtest bridge integration
Backtests must use the same:
- sizing rules
- stop assumptions
- gross exposure caps
- kill-switch-like abort semantics where possible

This is required so backtest results reflect execution philosophy rather than bypassing it.

## Config surface
Create `risk_config_v1` with:
- per_trade_risk_fraction
- max_symbol_notional_fraction
- max_portfolio_gross_fraction
- spread_bps_limits by strategy family
- micro_volatility_limits by strategy family
- max_concurrent_candidates
- session_loss_limit_fraction
- stale_data_seconds
- conflicting_family_rules

## Decision examples
### Example: allow
- trend alignment active
- regime uptrend tradable
- spread normal
- no conflicting exposure
- stop defined
- size within caps
Result: ALLOW

### Example: allow with warnings
- breakout active
- spread acceptable but elevated
- stop defined but wide
- size reduced by confidence and exposure cap
Result: ALLOW_WITH_WARNINGS

### Example: block
- strategy active but spread too wide
- current symbol already has conflicting mean-reversion position
Result: BLOCK

### Example: flatten only
- websocket stale or session loss limit breached
Result: FLATTEN_ONLY

## Required artifacts
- `risk_engine.py`
- `risk_models.py`
- `risk_config_v1.json`
- `risk_packet_examples_v1.json`
- tests: `test_risk_engine.py`, `test_risk_integration_flow.py`

## Acceptance criteria
Risk Engine v1 is complete when:
- strategy cannot become execution-ready without risk packet
- blocked entries record deterministic reasons
- size, stop, and exposure logic are inspectable in snapshots
- replay and backtest paths can call the same risk rules
- session-level kill switch can be simulated in tests
