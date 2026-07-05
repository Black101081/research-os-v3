# Indicator Thesis Library v1

Purpose: define indicator-level research theses so indicators are treated as interpretable analytical objects rather than decorative chart overlays.

## Thesis schema
Each indicator thesis should state:
- thesis_id
- indicator_family
- indicator_scope
- core_question
- information_edge
- non_edge_warning
- preferred_regimes
- avoid_regimes
- nearest_factor_dependencies
- nearest_indicator_neighbors
- signal_roles
- failure_archetypes
- misuse_patterns
- validation_targets

## Displacement and equilibrium theses

### Baseline displacement control thesis
- Core question: Is price stretched relative to recent equilibrium?
- Information edge: useful as a control measurement for stretch and local imbalance.
- Non-edge warning: raw stretch alone is not differentiated alpha.
- Preferred regimes: balanced ranges, orderly transition states.
- Avoid regimes: strong directional trends, event shocks.
- Signal roles: baseline recenter filter, equilibrium reference, contamination comparator.
- Failure archetypes: persistent tail occupancy, drifting equilibrium, trend acceleration.
- Misuse patterns: fading every extreme print without persistence or drift context.
- Validation targets: stretch persistence, false fade rate, recenter efficiency.

### Drift-aware equilibrium thesis
- Core question: Is price stretched relative to a moving rather than static equilibrium?
- Information edge: separates static-mean reversion from reversion against a drifting center.
- Non-edge warning: drift can be descriptive but not tradable if trend coherence remains too strong.
- Preferred regimes: weak trend drift, transition states, unstable balance.
- Avoid regimes: explosive breakouts, event repricing.
- Signal roles: drift-aware recenter, contamination filter, regime reinterpretation.
- Failure archetypes: equilibrium continues migrating, drift accelerates, structural break.
- Misuse patterns: treating every moving average deviation as reversion edge.
- Validation targets: drift gap half-life, contamination resistance, adverse excursion.

### Tail-persistence thesis
- Core question: Does time spent in extremes carry more information than raw distance alone?
- Information edge: distinguishes one-off stretch from persistent extremity exhaustion.
- Non-edge warning: extreme persistence can also mark genuine breakout acceptance.
- Preferred regimes: range edges, unstable transition zones.
- Avoid regimes: fresh trend initiation, event breakouts.
- Signal roles: persistence-aware fade, regime contamination alarm, signal confidence weighting.
- Failure archetypes: persistent acceptance, delayed reversal, event continuation.
- Misuse patterns: interpreting all persistence as exhaustion instead of acceptance.
- Validation targets: tail occupancy duration, reversal delay, continuation contamination.

## Trend and path theses

### Momentum alignment control thesis
- Core question: Is directional momentum aligned with prevailing path structure?
- Information edge: baseline continuation reference for trend-aware systems.
- Non-edge warning: simple crossover logic is common and should be treated as a control, not differentiated alpha.
- Preferred regimes: stable trends, orderly continuation.
- Avoid regimes: chop, ambiguous transitions.
- Signal roles: continuation control, trend state comparator, strategy benchmark.
- Failure archetypes: late entry, crossover lag, whipsaw clusters.
- Misuse patterns: promoting crossover logic without path-quality filters.
- Validation targets: lag cost, whipsaw rate, baseline continuation quality.

### Pullback quality thesis
- Core question: Is retrace structure healthy enough to support continuation?
- Information edge: distinguishes constructive pullbacks from structural damage.
- Non-edge warning: shallow pullbacks alone are not enough if coherence is breaking.
- Preferred regimes: orderly trends with recoverable pauses.
- Avoid regimes: chop, exhausted parabolic runs.
- Signal roles: continuation upgrade, late-entry reduction, structural filter.
- Failure archetypes: retrace deepens into failure, anchor misalignment, trend fragility.
- Misuse patterns: buying every small dip without structural quality check.
- Validation targets: reclaim success rate, pullback depth quality, drawdown containment.

### Reacceleration thesis
- Core question: Does trend force renew after an orderly pause?
- Information edge: targets timing improvement over always-on continuation logic.
- Non-edge warning: apparent reacceleration can be a final squeeze before exhaustion.
- Preferred regimes: established trends with clean pause behavior.
- Avoid regimes: event-driven reversals, unstable trend breaks.
- Signal roles: pause-to-renewal entry, chase reduction, coherence-aware continuation.
- Failure archetypes: false renewal, exhausted trend restart, pause breakdown.
- Misuse patterns: confusing volatility burst with coherent renewal.
- Validation targets: renewal selectivity, late-chase reduction, continuation persistence.

## Volatility theses

### Compression-release thesis
- Core question: Is low-volatility compression storing tradable expansion pressure?
- Information edge: useful when paired with pressure build-up and release quality, not compression alone.
- Non-edge warning: many squeezes resolve into noise or fakeouts.
- Preferred regimes: orderly transitions, trend resumptions.
- Avoid regimes: chaotic event states.
- Signal roles: breakout qualification, expansion readiness, release-quality gating.
- Failure archetypes: fake release, fragile compression, chaotic break.
- Misuse patterns: treating all low-vol states as breakout edge.
- Validation targets: orderly release rate, false breakout reduction, expansion persistence.

### Exhaustion-in-expansion thesis
- Core question: Is expansion already decaying rather than beginning?
- Information edge: separates fresh expansion from mature, exhaustible volatility states.
- Non-edge warning: exhaustion signals fail when expansion is actually the first leg of regime transition.
- Preferred regimes: late transition, unstable range edges.
- Avoid regimes: fresh breakout discovery.
- Signal roles: volatility fade, transition caution, expansion quality grading.
- Failure archetypes: second expansion wave, event continuation, trend handoff.
- Misuse patterns: fading all strong bars as exhausted.
- Validation targets: second-leg risk, reversal completion, event contamination.

## Participation and microstructure theses

### Conviction asymmetry thesis
- Core question: Is participation supporting one direction more credibly than the other?
- Information edge: improves directional filtering by measuring support quality, not just activity level.
- Non-edge warning: high participation can confirm both breakouts and exhaustion depending on context.
- Preferred regimes: breakouts, structured continuation, transition resolution.
- Avoid regimes: structurally quiet assets without meaningful volume structure.
- Signal roles: breakout confirmation, exhaustion divergence, direction-quality filter.
- Failure archetypes: noisy bursts, effort-result mismatch, late participation spike.
- Misuse patterns: equating higher volume with stronger edge in every context.
- Validation targets: direction support asymmetry, burst contamination, follow-through quality.

### Execution-readiness thesis
- Core question: Is the idea tradeable under real execution conditions?
- Information edge: converts microstructure from passive context into a promotion gate.
- Non-edge warning: execution state is a veto layer more often than a directional edge.
- Preferred regimes: any tradeable regime with nontrivial execution friction.
- Avoid regimes: synthetic historical series without tape realism.
- Signal roles: promotion gate, slippage hazard filter, liquidity trap avoidance.
- Failure archetypes: adverse selection, hidden fragility, false liquidity.
- Misuse patterns: mistaking execution readiness for direction prediction.
- Validation targets: bad-trade reduction, slippage avoidance, tradeability precision.
