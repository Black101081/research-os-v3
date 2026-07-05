# Expanded Signal Architecture v2

Purpose: extend the signal layer beyond common retail templates while preserving lineage from factor and indicator repositories.

## Design objectives
- Build a broader signal inventory from the expanded factor and indicator catalogs.
- Separate highly common templates from differentiated research signals.
- Keep every signal tied to explicit factors, indicators, regime fit, and failure logic.
- Make downstream strategy generation and validation easier.

## Five signal families
- Breakout and expansion
- Mean reversion and recenter
- Trend continuation and pullback
- Volatility transition and exhaustion
- Microstructure and execution-aware signals

## Signal template standard
Each signal must define:
- signal_id
- template_family
- tier
- thesis
- preferred_regimes
- avoid_regimes
- required_factors
- required_indicators
- trigger_logic
- invalidation_logic
- execution_note
- novelty_claim
- nearest_neighbors
- validator_checks

## Expansion target
- 4 signals per family
- 5 families
- Total: 20 signal templates
