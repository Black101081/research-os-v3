# Regime Thesis Library v1

A curated set of research theses organized by regime, describing expected signal behaviour
and risk posture under each market state.

---

## Uptrend

**Thesis**: In an established uptrend, trend-following signals extract positive expectancy
because price momentum tends to persist over short-to-medium horizons. Entry should be
aligned with the prevailing direction; fading the trend is penalized heavily.

**Key risk**: Late-entry after momentum exhaustion. Regime confidence decay is the primary
early-warning signal.

**Signal families that work**: trend_continuation, momentum_breakout  
**Signal families to avoid**: mean_reversion

---

## Downtrend

**Thesis**: Mirror of uptrend logic applied to the short side. Trend signals on the short
side extract positive expectancy. Mean-reversion signals have negative expectancy because
price continues to make lower lows.

**Key risk**: Short squeeze / forced liquidation reversal. Risk engine should monitor
`rel_volume_20` spike as a reversal warning.

**Signal families that work**: trend_continuation (short bias)  
**Signal families to avoid**: mean_reversion

---

## Range / Chop

**Thesis**: Price oscillates between support and resistance without sustained direction.
Mean-reversion signals extract value by fading extremes. Trend signals lose money by
chasing false breakouts.

**Key risk**: Range expanding into a true breakout. Bollinger width expansion above
threshold should trigger regime re-classification.

**Signal families that work**: mean_reversion, range_fade  
**Signal families to avoid**: trend_continuation, momentum_breakout

---

## Transition / Ambiguous

**Thesis**: Regime is in the process of switching or insufficient data exists to classify
reliably. Confidence is below the tradable threshold. All new entries should be blocked
to avoid buying into a regime that no longer exists.

**Key risk**: Missing a regime transition entry. Acceptable cost — it is better to miss
the first 5% of a new trend than to be caught long at the top of an old one.

**Signal families that work**: none  
**Signal families to avoid**: all

---

## Event-Driven / Volatile

**Thesis**: An external event (macro data release, large liquidation cascade, regulatory
shock) is driving abnormal volatility. Statistical models built on normal-distribution
assumptions break down. Risk engine blocks all entries regardless of signal direction.

**Key risk**: Missing a sharp directional move post-event. Acceptable cost — the
distribution tail risk is too large to trade with standard sizing.

**Signal families that work**: none  
**Signal families to avoid**: all

---

## Cross-Regime Notes

- Regime scope is stored per alpha at registration time (`regime_scope` field).
- The promotion engine should weight regime-match positively in scoring.
- A future v2 feature should implement **regime-specific promotion policies** where
  thresholds differ by regime (e.g. lower Sharpe bar in uptrend vs range_chop).
