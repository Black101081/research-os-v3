# Alpha Factory Roadmap v1

Purpose: define the roadmap that evolves Research OS V3 from a disciplined realtime research runtime into an Alpha Factory focused on research throughput, research quality, and research automation.

## North star
Move from:
- one researcher hand-writing a small set of signals
- manually backtesting and revising each idea

to:
- a system that can generate, validate, rank, store, and promote thousands of alpha candidates with human supervision.

## Core equation
Alpha Factory value = Research Throughput x Research Quality x Research Automation

A fast system with low-quality validation is noise.
A high-quality system with low throughput is bottlenecked.
The factory must improve all three dimensions together.

## Design principle
Earlier layers shape and discipline later layers.
- factor discovery shapes signal generation
- validation disciplines ranking
- ranking disciplines promotion
- registry disciplines lifecycle decisions

This must remain consistent with the existing Research OS V3 philosophy.

## Current starting point
Research OS V3 already has:
- live market ingestion
- OHLCV warmup/bootstrap
- factor and indicator pipeline
- regime layer
- signal orchestration
- strategy spec formation
- validation bridge
- playbook packet flow
- early risk and live-reactivity infrastructure

This is not yet an Alpha Factory, but it is a strong base layer.

## Future target architecture
Market Data
-> Factor Library
-> Factor Generator
-> Signal Generator
-> Validation Engine
-> Ranking Engine
-> Alpha Registry
-> Promotion / Demotion Engine
-> Runtime Candidate Set
-> Risk + Live Runtime Monitoring

## Phase 1: Foundation hardening
Goal: make current runtime trustworthy enough to support large-scale research generation.

Deliverables:
- complete live reactivity diff and message-level observability
- complete Risk Engine v1 integration into validation and strategy contracts
- unify replay path and live path semantics
- explicit error handling for missing signal toolkit or empty signal registry
- improve package import structure and runtime consistency

Exit criteria:
- runtime can explain downstream state changes per event
- strategy objects carry risk context
- research artifacts are reproducible across replay and live-normalized paths

## Phase 2: Factor Discovery Layer
Goal: turn factor research into a combinatorial search space instead of a manually curated list only.

Deliverables:
- normalized factor catalog with families, tags, dependencies, and anti-duplication metadata
- transforms: threshold, slope, rank, zscore, lag, spread, ratio, percentile, crossover
- candidate feature expressions generated from factor primitives
- factor validator to reject unstable, redundant, or invalid expressions

Typical candidate classes:
- A > threshold
- A rising for N bars
- A / B
- A - B
- A lagged vs current
- A in extreme percentile
- A confirms regime transition

Exit criteria:
- system can generate hundreds to thousands of factor-derived candidate expressions per symbol or regime family
- invalid and duplicate expressions are filtered automatically

## Phase 3: Signal Generator
Goal: automatically generate candidate signals from factor expressions and templates rather than hand-coding each signal.

Deliverables:
- signal template families: breakout, mean reversion, continuation, dispersion, regime switch, volatility event
- signal composition rules using factor expressions
- parameter grid definitions and pruning rules
- provisional signal objects with lineage back to factor expressions
- signal thesis templates attached to generated candidates

Exit criteria:
- candidate signal generation no longer requires writing one Python function per signal idea
- each generated signal records its provenance and assumptions

## Phase 4: Validation Engine
Goal: replace descriptive qualification with research-grade scoring.

Deliverables:
- standardized validation metrics: expectancy, Sharpe, Sortino, drawdown, turnover, capacity proxy, hit rate, regime robustness
- walk-forward and temporal split evaluation
- decay-aware metric tracking
- veto conditions for overfit, unstable, low-capacity, high-friction candidates
- validator reports suitable for ranking and registry storage

Exit criteria:
- each alpha candidate receives a structured validation packet and research score
- promotion decisions depend on validation scores, not only activation state

## Phase 5: Ranking Engine
Goal: sort alpha candidates by usefulness, not only by raw return.

Deliverables:
- composite research score
- penalization for redundancy, turnover, fragility, and regime over-concentration
- diversification-aware ranking rules
- novelty scoring against registry history
- rank snapshots per symbol, universe, and regime

Exit criteria:
- top candidates can be queried by regime, factor family, decay profile, and score bucket

## Phase 6: Alpha Registry
Goal: persist alpha knowledge as a first-class research asset.

Registry stores:
- alpha id and lineage
- factor dependencies
- signal definition and parameters
- validation history
- regime-specific performance
- lifecycle state
- decay profile
- promotion and demotion decisions

Exit criteria:
- system can answer questions like:
  - best BTC alpha in trend regime over last 30 days
  - low-correlation candidates versus active runtime set
  - candidates recently demoted for decay

## Phase 7: Lifecycle management
Goal: treat alphas as evolving assets, not permanent truths.

Deliverables:
- states: draft, validated, promoted, shadow, active, quarantined, demoted, retired
- automatic decay detection
- regime mismatch detection
- revalidation scheduling
- demotion and quarantine policies

Exit criteria:
- poor or decaying alphas are automatically downgraded or removed from the active set

## Phase 8: AI Research Agent layer
Goal: use AI to navigate the research graph, not to predict price directly.

Use cases:
- query top alphas by symbol, regime, and horizon
- discover underexplored factor combinations
- suggest low-correlation extensions to active alpha set
- summarize why a candidate was promoted or demoted
- generate research briefs from registry evidence

Exit criteria:
- the agent operates over structured registry data and validation outputs, not hallucinated market intuition

## Core data products required
- factor catalog
- signal candidate catalog
- validation scorecards
- alpha registry
- lifecycle event log
- regime-aware performance panels

## Governance rules
- no alpha may be promoted without validation scorecard
- no active alpha may bypass risk and runtime health gates
- no generated signal may enter ranking without lineage metadata
- no decay decision may be made without historical comparison window

## Key KPIs
- candidate generation count per week
- validation throughput per day
- duplicate rejection rate
- promoted alpha survival rate
- decay detection lead time
- active alpha diversity by regime and factor family

## v1 implementation priorities
1. factor catalog and generator primitives
2. signal generator templates and candidate lineage
3. validation score schema
4. alpha registry schema and persistence rules
5. lifecycle state machine

## Acceptance criteria
Alpha Factory Roadmap v1 is successful when Research OS V3 has a credible path from runtime research infrastructure to automated alpha discovery, scoring, storage, and lifecycle control.
