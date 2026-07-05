# Strategy Refinement Pass v1

Purpose: upgrade strategy families from generic PASS_WITH_WARNINGS structures toward higher-quality promotion logic.

## Main changes
- Promotion rules now require explicit improvement over baseline controls instead of generic acceptance language.
- Validation focuses now test differentiated edge, not just generic profitability or drawdown.
- Risk focuses now include regime vetoes, fragility checks, and execution-specific abort logic.

## Design effect
- Breakout families now compete against baseline breakouts on quality and execution stability.
- Mean-reversion families now must prove drift-aware or tail-persistence advantage.
- Trend families now must prove coherence, pullback quality, or reacceleration timing edge.
- Execution overlays now must show measurable bad-trade reduction rather than decorative filtering.
