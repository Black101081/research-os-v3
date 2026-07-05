# Regime Engine Spec v1

## Overview

The regime engine classifies the current market state into one of five canonical regimes.  
Classification drives signal gating — only signals whose `preferred_regimes` overlap with the
current regime are allowed to activate.

## Regime Taxonomy

| Regime ID              | Label               | Tradability | Preferred Families                        |
|------------------------|---------------------|-------------|-------------------------------------------|
| `uptrend`              | Uptrend             | tradable    | trend_continuation, momentum_breakout     |
| `downtrend`            | Downtrend           | tradable    | trend_continuation                        |
| `range_chop`           | Range / Chop        | restricted  | mean_reversion, range_fade                |
| `transition_ambiguous` | Transition/Ambiguous| blocked     | none                                      |
| `event_driven`         | Event-Driven        | blocked     | none                                      |

## Primary Classification Factors

- `ret_5` — 5-bar return
- `macd` vs `macd_signal` — momentum direction
- `zscore_close_20` — price relative to 20-bar rolling mean
- `volatility_20` — rolling realised volatility
- `rel_volume_20` — relative volume vs 20-bar mean
- `bollinger_width` — band width as proxy for range compression

## Confidence Thresholds

- **Tradable**: confidence ≥ 0.55
- **Restricted**: 0.40 ≤ confidence < 0.55
- **Blocked**: confidence < 0.40 OR regime is `transition_ambiguous` / `event_driven`

## Lifecycle Integration

The regime at the time of alpha registration is stored in `regime_at_creation` inside the
strategy spec. Promotion/demotion decisions can be regime-scoped in a future v2 policy.

## Engine File

`regime_engine.py` — implements `RegimeEngine.classify(factors) -> regime_state`

`regime_state` schema:
```json
{
  "regime": "uptrend",
  "confidence": 0.72,
  "tradable": true,
  "why": { "ret_5": 0.006, "macd": 1.24, ... }
}
```

## Registry

`research_knowledge/regime_registry.json` — canonical list of regime definitions.
