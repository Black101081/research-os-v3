# Alpha Registry Spec v1

Purpose: define the first persistent schema for storing alpha candidates, their lineage, validation outcomes, regime behavior, and lifecycle state.

## Role in architecture
The Alpha Registry is the memory system of the Alpha Factory.
It is not just a log of backtests.
It is a structured knowledge base for generated and hand-authored alpha candidates.

## Core requirements
The registry must answer:
- what is this alpha?
- where did it come from?
- what factors and signal template created it?
- how did it perform overall and by regime?
- is it improving, stable, or decaying?
- should it be promoted, held, quarantined, or retired?

## Entity types
### 1. Alpha definition
Fields:
- alpha_id
- alpha_name
- source_type: generated / manual / imported
- symbol_scope
- universe_scope
- timeframe
- regime_scope
- factor_dependencies
- indicator_dependencies
- signal_template_family
- signal_expression
- parameter_set
- thesis_summary
- lineage_parent_ids
- created_at
- created_by

### 2. Validation scorecard
Fields:
- alpha_id
- validation_run_id
- sample_window
- train_window optional
- test_window
- walk_forward_slice_id optional
- expectancy
- sharpe
- sortino
- drawdown_max
- turnover
- capacity_proxy
- win_rate
- profit_factor optional
- stability_score
- overfit_risk_score
- research_score
- validation_status
- rejection_reasons
- created_at

### 3. Regime performance panel
Fields:
- alpha_id
- regime_name
- trade_count
- expectancy
- sharpe
- drawdown_max
- turnover
- hit_rate
- robustness_score
- created_at

### 4. Decay profile
Fields:
- alpha_id
- observation_window
- prior_research_score
- current_research_score
- delta_score
- prior_sharpe
- current_sharpe
- prior_expectancy
- current_expectancy
- decay_flag
- decay_reason
- created_at

### 5. Lifecycle event
Fields:
- alpha_id
- event_type: created / validated / promoted / shadowed / activated / quarantined / demoted / retired / revalidated
- previous_state
- new_state
- trigger_reason
- supporting_validation_run_id optional
- created_at

## Minimal storage model
Alpha Registry v1 can begin with append-only JSONL or DuckDB-backed tables.
Required logical tables:
- alpha_definitions
- validation_scorecards
- regime_panels
- decay_profiles
- lifecycle_events

## Identity and lineage
Every alpha must have a stable `alpha_id`.
Generated candidates must also carry:
- factor expression id
- signal template id
- parameter grid id or hash
- parent alpha ids if derived from an earlier candidate

This is required for traceability and anti-duplication.

## State machine
Allowed states:
- draft
- validated
- promoted
- shadow
- active
- quarantined
- demoted
- retired

Transitions:
- draft -> validated
- validated -> promoted or demoted
- promoted -> shadow or active
- active -> quarantined or demoted
- quarantined -> active or retired
- demoted -> revalidated or retired

No direct draft -> active transition is allowed.

## Query patterns
Registry must support queries such as:
- top BTC alphas by research_score in trend regime
- candidates with low correlation to active set
- mean-reversion alphas decaying in last 30 days
- generated signals from factor family X with robust downside control
- candidates blocked from promotion due to capacity or turnover

## Regime awareness
Each alpha can have both:
- global scorecard
- regime-specific scorecards

Promotion decisions should consider regime-specific fit, not only pooled performance.

## Decay tracking rules
Decay should be computed over rolling windows.
Suggested v1 triggers:
- research_score drop beyond threshold
- Sharpe drop beyond threshold
- expectancy deterioration beyond threshold
- rising drawdown severity
- instability across adjacent windows

Decay does not automatically retire an alpha, but it must create a lifecycle event and review requirement.

## Integration points
### Signal generator
- writes draft alpha definitions

### Validation engine
- writes validation scorecards and regime panels

### Ranking engine
- reads latest validated records and research scores

### Promotion engine
- writes lifecycle events and state transitions

### AI research agent
- queries registry as the source of truth for discovery and explanation

## Anti-duplication rules
Registry should reject or flag candidates that are:
- identical by expression and parameters
- semantically equivalent by normalized expression form
- too correlated with existing active candidates if policy forbids it

## Metadata requirements
Each registry record should include:
- schema_version
- created_at
- tags
- notes optional
- provenance

## Deliverables
- `alpha_registry_spec_v1.md`
- `alpha_registry_schema_v1.json`
- `alpha_lifecycle_states.md`
- future code modules: `alpha_registry.py`, `alpha_registry_store.py`

## Acceptance criteria
Alpha Registry v1 is complete when generated and manual alpha candidates can be stored with lineage, validation history, regime behavior, decay profile, and lifecycle state in a queryable form.
