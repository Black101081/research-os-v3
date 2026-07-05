# Novelty Refinement Pass v2

This pass upgrades baseline templates by explicitly labeling them as control objects and shifting promotion preference toward differentiated variants.

## Refined baseline controls
- bollinger_squeeze_breakout -> kept as breakout control, no longer implied as preferred edge source.
- zscore_recenter -> kept as mean-reversion control, with drift-aware and tail-persistence variants preferred for promotion.
- macd_trend_continuation -> kept as continuation control, with pullback-quality and reacceleration variants preferred for promotion.

## Refinement effect
- Baseline templates remain valuable for comparison and sanity testing.
- Differentiated templates now carry stronger novelty language and clearer promotion logic.
- Strategy promotion rules now explicitly require improvement over baseline controls.
