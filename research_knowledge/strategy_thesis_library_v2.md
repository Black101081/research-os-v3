# Strategy Thesis Library v2

Purpose: define strategy-level theses as research claims that must beat baseline controls, survive execution realism, and pass lifecycle validation.

## Strategy thesis schema
- strategy_family
- parent_signal_families
- baseline_controls
- differentiated_claim
- why_now_logic
- execution_realism_assumptions
- portfolio_role
- promotion_requirements
- rejection_requirements
- failure_archetypes
- negative_knowledge_targets
- validation_targets

## Family theses

### Breakout confirmation thesis
- Baseline controls: raw squeeze breakout, simple expansion break.
- Differentiated claim: breakout should only matter when pressure build-up, release quality, and execution stability jointly improve quality.
- Why-now logic: confirmation exists to reduce fakeouts and low-quality trigger frequency.
- Execution realism assumptions: fills deteriorate during expansion; slippage resilience matters.
- Promotion requirements: better follow-through, lower fakeout rate, acceptable slippage damage.
- Rejection requirements: filter removes too many good trades or fails to reduce bad ones.
- Failure archetypes: fragile compression, late confirmation, trapped liquidity.
- Validation targets: baseline_breakout_lift, filter_precision, execution_stability.

### Equilibrium recenter thesis
- Baseline controls: raw z-score fade, simple band reversion.
- Differentiated claim: reversion should beat baseline only when drift-awareness or tail persistence clarifies exhaustion versus acceptance.
- Why-now logic: ordinary stretch is too generic; differentiated recenter must resist contamination.
- Execution realism assumptions: fading into trend continuation can cause adverse excursion quickly.
- Promotion requirements: lower contamination rate, better recenter efficiency, tighter adverse excursion.
- Rejection requirements: too many fades during genuine trend continuation.
- Failure archetypes: acceptance mistaken for exhaustion, drift migration, event shock continuation.
- Validation targets: contamination_resistance, recenter_efficiency, mae_containment.

### Trend alignment thesis
- Baseline controls: generic MACD or crossover continuation.
- Differentiated claim: path quality, pullback structure, and coherence retention should improve continuation quality beyond naive alignment.
- Why-now logic: not all momentum alignment is tradable; quality of path matters.
- Execution realism assumptions: late entries degrade expectancy and amplify reversal pain.
- Promotion requirements: improved drawdown containment, reduced late-entry penalty, better retention quality.
- Rejection requirements: small edge disappears after realistic costs or coherence filters lag too much.
- Failure archetypes: exhausted trend continuation, false reacceleration, path break.
- Validation targets: baseline_crossover_lift, coherence_retention, late_entry_penalty_reduction.

### Execution-aware overlay thesis
- Baseline controls: ungated directional systems, naive tradeability checks.
- Differentiated claim: overlays should improve system quality by vetoing trades with hidden execution risk.
- Why-now logic: avoiding bad trades can add more value than generating extra directional entries.
- Execution realism assumptions: slippage, adverse selection, and liquidity traps are first-order effects.
- Promotion requirements: measurable bad-trade reduction with acceptable opportunity loss.
- Rejection requirements: overlay blocks too much opportunity or acts only as decorative friction.
- Failure archetypes: false vetoes, noisy hazard spikes, over-filtering.
- Validation targets: bad_trade_reduction, slippage_avoidance_delta, opportunity_preservation.
