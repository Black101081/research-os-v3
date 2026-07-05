# Factor Expression Grammar v1

Purpose: define the first constrained grammar for generating interpretable factor expressions from the catalog.

## Goal
The grammar must be expressive enough to produce useful candidate signals, but restricted enough to avoid symbolic explosion and unreadable candidates.

## Primitive expression forms
### 1. Level threshold
- `A > x`
- `A < x`
- `A >= x`
- `A <= x`

### 2. Directional change
- `rising(A, n)`
- `falling(A, n)`
- `delta(A, n) > x`
- `delta(A, n) < x`

### 3. Cross and crossover
- `crosses_above(A, B)`
- `crosses_below(A, B)`
- `A > B`
- `A < B`

### 4. Spread and ratio
- `(A - B) > x`
- `(A - B) < x`
- `(A / B) > x`
- `(A / B) < x`

### 5. Percentile and rank
- `pct_rank(A, n) > p`
- `pct_rank(A, n) < p`
- `in_top_percentile(A, n, p)`
- `in_bottom_percentile(A, n, p)`

### 6. Lag relation
- `lag(A, k) < A`
- `lag(A, k) > A`
- `A - lag(A, k) > x`

### 7. Bounded conjunctions
- `(expr1) and (expr2)`
- `(expr1) and (expr2) and (expr3)`

No conjunction may exceed depth 3 in v1.

## Domain constraints
- Max factors per candidate: 3.
- Max lags: 10 bars unless explicitly overridden.
- Max ratio nesting depth: 1.
- No recursive nested conjunction groups.
- No opaque functions without human-readable normalization.

## Regime hints
Expressions may carry optional regime hints:
- `preferred_regime = uptrend | downtrend | range_chop | high_volatility | transition_ambiguous`
- `avoid_regime = ...`

## Example normalized expressions
- `ema_spread_8_21 > 0`
- `zscore_close_20 < -1.5 and micro_volatility_20 < 0.004`
- `crosses_above(MACD, MACD_signal) and ret_5 > 0`
- `BollingerWidth < 0.03 and live_ret_from_last_close > 0.001`
- `trade_flow_imbalance_20 > 0.2 and spread_bps < 5`

## Anti-duplication rules
Expressions normalize by:
- ordering commutative comparisons consistently where valid
- removing whitespace variants
- canonicalizing aliases
- rounding parameter grids to configured precision

Equivalent normalized expressions should be flagged or rejected before validation.
