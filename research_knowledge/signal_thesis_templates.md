# Signal Thesis and Template Library

Purpose: define the conceptual thesis and machine-usable template for each supported signal family.

## Template schema
Each signal template should specify:
- thesis
- template_family
- preferred_regimes
- avoid_regimes
- required_factors
- required_indicators
- trigger_logic
- invalidation_logic
- why_fields
- execution_readiness_logic

## Supported templates

### bollinger_squeeze_breakout
- Template family: breakout
- Thesis: compression can precede directional expansion; breakouts improve when participation confirms release from a low-volatility state.
- Preferred regimes: uptrend, downtrend, transition_ambiguous.
- Avoid regimes: range_chop, event_driven.
- Required indicators: BollingerWidth, RelativeVolume.
- Trigger logic: squeeze is true, breakout is true, relative volume passes threshold, regime is acceptable.
- Invalidation logic: breakout fades back into compression or participation disappears.
- Execution note: should prefer entries with explicit expansion confirmation.

### zscore_recenter
- Template family: mean_reversion
- Thesis: temporary displacement from local equilibrium can revert when structure stays balanced and trend pressure is weak.
- Preferred regimes: range_chop.
- Avoid regimes: uptrend, downtrend, high_volatility.
- Required factors: zscore_close_20.
- Trigger logic: z-score breach enters oversold/overbought recenter zone and regime remains balanced.
- Invalidation logic: displacement continues while regime becomes directional.
- Execution note: should be size-conservative in unstable volatility.

### macd_trend_continuation
- Template family: trend_continuation
- Thesis: join an already established directional move when momentum resumes in the same direction after alignment is present.
- Preferred regimes: uptrend, downtrend.
- Avoid regimes: range_chop, transition_ambiguous, event_driven.
- Required indicators: MACD, MACD_signal.
- Trigger logic: MACD is aligned over signal for bullish continuation or below signal for bearish continuation, with regime compatibility.
- Invalidation logic: momentum cross reverses or regime loses tradable directional structure.
- Execution note: should pair with trend-aware exits rather than fixed short-horizon mean targets.

## Research priorities
- Expand templates into long and short variants explicitly.
- Add score-based confidence instead of binary activation only.
- Add templates for volatility expansion fade, pullback continuation, and exhaustion reversal.
