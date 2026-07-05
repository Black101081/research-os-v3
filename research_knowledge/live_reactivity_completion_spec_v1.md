# Live Reactivity Completion Spec v1

Purpose: complete the live runtime path so changes in BTC or any subscribed symbol propagate through factors, indicators, regime, signals, strategies, and risk state in a measurable and testable way.

## Problem statement
The original runtime proved websocket connectivity, but trade-only updates did not reliably change research-layer state because factor and indicator calculations depended primarily on closed bars.

The system must move from:
- market data updates last_trade only

to:
- market data updates live bar state
- live bar updates factor state
- factor state updates indicators
- indicators update regime and signals
- downstream changes are observable per message

## Core principle
Every meaningful market event must have a defined propagation path and a measurable downstream footprint.

## Reactivity layers
### Layer 1: data ingestion
Inputs:
- trades
- bbo
- candle
- allMids optional context

Requirements:
- no silent drop of subscribed channels
- malformed payloads produce warnings or counters
- each message gets a normalized routing path

### Layer 2: forming bar state
Trades and BBO updates should be able to mutate a `current_bar` or equivalent intrabar state.

Required fields:
- current_bar.ts
- current_bar.open
- current_bar.high
- current_bar.low
- current_bar.close
- current_bar.volume
- current_bar_source

Rules:
- trade updates mutate close/high/low/volume
- candle close reconciles and replaces the official bar
- current bar must not silently overwrite finalized history without timestamp match

### Layer 3: micro factors
Add tick-reactive factors that do not require bar close.

Required minimum set:
- tick_ret_1
- tick_ret_5
- trade_zscore_20
- micro_volatility_20
- trade_flow_imbalance_20
- spread_bps
- live_ret_from_last_close
- last_trade_minus_mid_bps

These factors are intended to shape and discipline later layers, not replace bar-based factors. They are especially important for execution gating and intrabar caution. [cite:417]

### Layer 4: live indicators
Create indicator aliases or live variants from micro factors.

Required minimum set:
- TradeFlowImbalance
- MicroVolatility
- SpreadBps
- LiveReturnFromClose

Optional live variants later:
- LiveMACD
- IntrabarBollingerWidth
- DriftFromLiveMid

## Evaluation modes
Runtime must support at least three modes:
- `tick`: lightweight reactive update
- `intrabar`: current bar and micro factors refreshed
- `bar_close`: full bar-confirmed refresh

Mode semantics:
- tick mode should avoid expensive full validation when possible
- bar_close mode should recompute full validation packet
- intrabar mode may update execution readiness and warnings without final promotion

## Downstream propagation rules
### Factors
- bar-based factors may include current forming bar when configured
- micro factors always update on trade/BBO events where data permits

### Indicators
- live indicators update when parent micro factors change
- bar indicators update when current bar materially changes if include_current is enabled

### Regime
- regime may be recomputed intrabar, but should expose whether state is provisional or bar-confirmed

### Signals
- signal output must indicate whether trigger is intrabar or confirmed
- intrabar signal cannot be promoted as confirmed without explicit rule

### Strategies
- strategies may move from standby -> candidate intrabar
- execution_ready requires both strategy logic and risk permission
- reactive_source must be recorded, e.g. `live_intrabar` or `bar_close`

## Reactivity observability
Every message-level test should be able to answer:
- did current_bar change?
- which factors changed?
- which indicators changed?
- did regime change?
- did any signal activation state change?
- did any strategy execution readiness change?
- did risk packet change?

Required artifacts:
- structured diff packet per processed message
- counters for each changed layer
- optional rolling summary for UI and test reports

## Diff packet spec
Create `reactivity_diff_v1` with:
- symbol
- message_type
- processed_at
- current_bar_changed
- factors_changed: [field names]
- indicators_changed: [field names]
- regime_changed
- signals_changed: [signal names]
- strategies_changed: [strategy names]
- risk_changed
- validation_changed
- reactive_source

This diff packet is mandatory for testing and debugging.

## Runtime performance rules
Do not recompute everything blindly on every message.

Use these constraints:
- tick mode updates only affected fields
- validation packet can be partially refreshed intrabar and fully rebuilt on bar close
- registry writes should remain periodic rather than on every tick
- expensive candidate promotion logic should run on state transitions, not on every message

## Consistency rules
- official candle close has precedence over provisional current_bar
- intrabar state must never create lookahead semantics
- replay path and live path should use the same propagation logic where possible
- missing signal toolkit or empty registry should produce explicit warnings, not silent empty output

## Failure handling
Track and surface:
- dropped message count
- parse failures
- stale symbol state
- reactivity disabled or degraded mode
- repeated unchanged downstream states despite large price movement

## Tests required
### Unit tests
- current bar mutates correctly with trade sequence
- bbo updates spread_bps and mid-derived factors
- candle reconciliation preserves finalized history
- diff packet records exact changed fields

### Integration tests
- warmup + live trade sequence changes at least one factor and one indicator
- intrabar signal appears as provisional, not confirmed
- bar close can confirm or cancel provisional state
- risk packet reacts to spread or micro volatility deterioration

### Regression tests
- no reintroduction of trade-only last_trade updates with zero downstream reactivity
- historical replay path produces same factor/indicator sequence as normalized live feed when given equivalent events

## Deliverables
- `reactivity_engine.py` or extension inside `realtime_engine.py`
- `reactivity_diff.py`
- `live_bar_builder.py`
- `micro_factor_library.md`
- tests: `test_live_reactivity.py`, `test_reactivity_diff.py`, `test_live_bar_reconciliation.py`

## Acceptance criteria
Live Reactivity Completion v1 is complete when:
- BTC live trade movement changes measurable downstream state
- at least one factor and one indicator can change intrabar
- reactivity diff packet shows exactly what changed per event
- signal and strategy transitions can be classified as provisional vs confirmed
- runtime avoids unnecessary full recomputation on every message
