# Indicator Library

Purpose: define the interpretation layer that transforms factors and raw bar sequences into richer state objects for regime detection and signal templates.

## Design principles
- Indicators are not a replacement for factors; they are structured interpretations built on top of factors or direct price history.
- Each indicator should state: core meaning, parameterization, regime fit, overlap with factors, and misuse risks.

## Indicators

### MACD
- Definition: difference between fast EMA and slow EMA, with signal line and histogram.
- Parameters in V3: 12, 26, 9.
- Interpretation: momentum continuation and directional acceleration proxy.
- Best fit: trend continuation, transition monitoring.
- Overlap: related to ema_spread_8_21, but captures acceleration through multi-EMA structure.
- Misuse risk: crossover-only usage in chop creates false positives.

### BBANDS_mid / upper / lower
- Definition: 20-bar mean and 2-standard-deviation envelope.
- Interpretation: local equilibrium and dispersion envelope.
- Best fit: compression detection, mean reversion context, breakout framing.
- Overlap: uses same statistical base as zscore_close_20 and volatility_20.
- Misuse risk: bands expand after shock; static breakout rules can react too late.

### BollingerWidth
- Definition: (upper - lower) / mid.
- Interpretation: direct compression and expansion proxy.
- Best fit: squeeze-breakout template and volatility regime scoring.
- Overlap: heavily related to volatility_20.
- Misuse risk: compression alone is not directional information.

### ZScore_Close
- Definition: indicator-form expression of standardized close displacement.
- Interpretation: convenience bridge from factor layer into signal layer.
- Best fit: mean reversion template.
- Overlap: same logic as zscore_close_20.
- Misuse risk: should not be treated as independent evidence from zscore_close_20.

### RelativeVolume
- Definition: indicator-form expression of rel_volume_20.
- Interpretation: participation confirmation.
- Best fit: breakout template, event-validation filter.
- Overlap: same logic as rel_volume_20.
- Misuse risk: low activity does not always invalidate a trade in structurally quiet assets.

## Expansion roadmap
- Add RSI family for bounded momentum context.
- Add ATR and Keltner families for range-aware volatility interpretation.
- Add structure indicators: ADX, Supertrend, Donchian, VWAP displacement.
- Add order-flow indicators once microstructure features are stable.
