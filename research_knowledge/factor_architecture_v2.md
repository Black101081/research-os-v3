# Expanded Factor Architecture v2

Purpose: define a research-grade taxonomy for factor development in Research OS V3 so expansion happens with quality control instead of random accumulation.

## Design objectives
- Reach high breadth without collapsing into duplicated or trivial variants.
- Separate common baseline factors from differentiated research factors.
- Preserve lineage from factor -> indicator -> signal -> strategy -> validation.
- Make every factor evaluable by structural and research validators.

## Five factor families

### 1. Return and displacement
Core question: how far and how fast price has moved relative to recent history or equilibrium.
Research role: directional impulse, stretch, exhaustion, recenter opportunity, transition pressure.

### 2. Trend and path structure
Core question: whether motion is aligned, persistent, decaying, or internally unstable.
Research role: trend continuation, pullback quality, path dependency, directional state confidence.

### 3. Volatility and compression
Core question: whether the market is compressed, expanding, shocked, or fragile.
Research role: squeeze logic, breakout readiness, stop placement, risk scaling, regime classification.

### 4. Participation and conviction
Core question: whether activity, volume, and follow-through support a move or contradict it.
Research role: breakout confirmation, event filtering, exhaustion detection, false-move rejection.

### 5. Microstructure and execution state
Core question: whether spread, imbalance, aggressor flow, and local liquidity support execution and signal quality.
Research role: execution readiness, liquidity gating, short-horizon instability detection, quote pressure.

## Three research tiers
- Core tier: robust, interpretable, likely portable across symbols and venues.
- Edge tier: less common but still grounded in clear market logic.
- Frontier tier: deliberately differentiated factors that combine multiple dimensions and may produce unique signal edges.

## Anti-duplication rules
- Changing only lookback does not create a new research-grade factor unless the economic interpretation changes.
- A factor must state what information it adds beyond its nearest neighbor.
- Indicator-form restatements of the same underlying quantity should remain indicators, not new factors.
- Every factor must list a likely failure mode and a regime where it should underperform.

## Required fields for every factor candidate
- factor_id
- family
- tier
- title
- intuition
- formula_sketch
- inputs
- preferred_regimes
- avoid_regimes
- nearest_neighbors
- novelty_claim
- failure_modes
- downstream_uses
- validator_checks

## Expansion standard
Each family should eventually contain:
- 5 core factors
- 7 edge factors
- 8 frontier factors
Total per family: 20
Total across five families: 100
