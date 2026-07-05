# Novelty Refinement Plan v1

Purpose: upgrade high-breadth repositories from PASS_WITH_WARNINGS toward PASS by targeting the most common or lowest-novelty templates first.

## Priority targets
- `ret_1`, `ret_3`, `ret_5`: keep as baseline factors, but explicitly mark them as control features rather than differentiated research factors.
- `ZScore_Close`, `RelativeVolume`, `MACD`, `BollingerWidth`: keep as anchor indicators, but pair them with richer composite indicators for differentiated usage.
- `zscore_recenter`: refine into drift-aware, tail-persistence, and shock-decay variants.
- `bollinger_squeeze_breakout`: refine into pressure-aware, fragility-aware, and execution-gated breakout variants.
- `macd_trend_continuation`: refine into pullback-quality, reacceleration, and execution-readiness continuation variants.

## Refinement rules
- Core templates may remain common, but must be labeled as baseline controls.
- Edge and frontier templates must state what they add beyond the baseline control.
- Promotion preference should favor templates that improve filter quality, execution safety, or regime specificity rather than just signal frequency.
- A template with novelty below differentiated threshold should remain usable but not be prioritized for promotion.

## Differentiation heuristics
- Prefer pre-break pressure over observed breakout alone.
- Prefer time-in-extreme or drift-aware reversion over raw z-score alone.
- Prefer reacceleration and pullback-quality continuation over generic crossover continuation.
- Prefer execution vetoes and liquidity filters over direction-only signals in marginal conditions.
