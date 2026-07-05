# Signal Generator Spec v1

Purpose: define the first automated signal generation layer that transforms factor primitives and templates into candidate alpha signals with lineage and validation-ready metadata.

## Role in architecture
Signal Generator sits between Factor Discovery and Validation.
It converts factor expressions into candidate signal definitions.

Pipeline:
Factor Catalog
-> Factor Expressions
-> Signal Templates
-> Candidate Signals
-> Validation Queue
-> Alpha Registry Draft Entries

## Why it exists
Hand-writing each signal is a throughput bottleneck.
Signal Generator v1 must allow the system to create many candidate signals without losing interpretability.

## Inputs
Required inputs:
- factor catalog
- indicator catalog optional
- signal template library
- generation config
- anti-duplication rules
- regime constraints optional

## Output object
Each generated candidate must produce a `signal_candidate_v1` with:
- signal_candidate_id
- signal_name
- source_expression_ids
- template_family
- regime_scope
- symbol_scope
- timeframe
- parameter_set
- trigger_definition
- confirmation_definition optional
- invalidation_definition optional
- thesis_summary
- tags
- created_at
- lineage_metadata
- validation_status: draft

## Template families for v1
Required initial families:
- breakout
- mean_reversion
- continuation
- volatility_event
- regime_transition

These families should align with the existing signal toolkit and strategy thesis templates where possible.

## Factor expression primitives
Supported primitive forms in v1:
- level threshold: A > x, A < x
- directional change: A rising, A falling
- cross / crossover: A crosses B
- spread / difference: A - B > x
- ratio: A / B > x
- percentile extreme: A in top or bottom p percentile
- lag relation: A_t > A_t-k
- multi-condition conjunctions limited to small depth

## Generation rules
### Rule 1: interpretability first
Generated expressions must remain understandable by a human researcher.
No opaque symbolic explosion in v1.

### Rule 2: bounded combinatorics
Use caps on:
- maximum factors per candidate
- maximum conjunction depth
- parameter grid size
- maximum lags

### Rule 3: lineage required
Every candidate must record:
- source factors
- template family
- parameter values
- generation rule id

### Rule 4: regime compatibility
Signal generator may attach suggested regime scopes based on factor family or template metadata.

## Example generated candidates
Examples:
- breakout: BollingerWidth < p20 and ret_5 rising and price breaks BBANDS_upper
- mean_reversion: zscore_close_20 < -1.5 and micro_volatility_20 moderate
- continuation: MACD > MACD_signal and ema_spread_8_21 positive and regime uptrend
- volatility_event: spread_bps stable and micro_volatility_20 expanding

## Parameter handling
Each template has bounded parameters.
Example:
- threshold grid
- lookback grid
- lag grid
- percentile grid
- confirmation window grid

Signal Generator v1 should produce parameterized candidates, but must keep the search space controlled.

## Anti-duplication and pruning
Prune candidates that are:
- syntactically identical
- normalized-equivalent
- logically contradictory
- unsupported by required inputs
- outside allowed regime scope
- too complex for v1 interpretability rules

Optional pruning:
- highly correlated candidate family members after a quick precheck

## Candidate quality gates before validation
A generated candidate should be dropped early if:
- required factor inputs are missing
- trigger definition never fires in sample precheck
- signal frequency is zero or absurdly high
- expression violates domain rules

## Integration with thesis templates
Each signal candidate should map to a thesis template containing:
- what edge it targets
- preferred regimes
- likely failure mode
- execution sensitivities
- invalidation cues

This keeps generation aligned with the user’s signal-thesis framework.

## Integration with alpha registry
Every generated candidate should immediately create a draft Alpha Registry entry with:
- generated source type
- lineage metadata
- template family
- expression signature
- initial tags

## Generation config v1
Suggested config fields:
- enabled_template_families
- max_candidates_per_batch
- max_factors_per_candidate
- max_conjunction_depth
- threshold_grid
- lag_grid
- percentile_grid
- allowed_regime_scopes
- anti_duplication_policy

## Evaluation handoff
Signal Generator does not decide promotion.
It only creates candidates and sends them to:
- validation queue
- registry draft writer

## Deliverables
- `signal_generator_spec_v1.md`
- `signal_template_library_v1.json`
- `factor_expression_grammar_v1.md`
- future code modules: `signal_generator.py`, `candidate_pruner.py`, `signal_lineage.py`

## Acceptance criteria
Signal Generator v1 is complete when the system can automatically produce interpretable, lineage-aware, validation-ready signal candidates from factor primitives and template families without requiring one bespoke hand-written function per idea.
