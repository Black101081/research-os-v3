# Factor Library

Purpose: define the atomic market descriptors used by Research OS V3 before indicator interpretation, signal activation, and strategy synthesis.

## Design principles
- Factors are the lowest-level interpretable measurements derived directly from bars, trades, and order-state context.
- Indicators may reuse factors, but factors should remain simple, composable, and stable across multiple strategies.
- Every factor should state: intuition, formula, lookback, regime fit, failure modes, and downstream signal usage.

## Factor families

### 1. Return and displacement
#### ret_1
- Definition: one-bar return.
- Formula: close_t / close_t-1 - 1.
- Interpretation: captures immediate directional impulse.
- Stronger use cases: micro-momentum, breakout confirmation, early transition detection.
- Failure modes: noisy in chop; highly unstable when liquidity is thin.
- Downstream usage: regime transition checks, short-horizon momentum conditions.

#### ret_5
- Definition: five-bar return.
- Formula: close_t / close_t-5 - 1.
- Interpretation: smoother directional displacement than ret_1.
- Stronger use cases: regime classification and directional persistence checks.
- Failure modes: can lag turning points; can overstate persistence during event-driven spikes.
- Downstream usage: regime_engine directional bias.

#### zscore_close_20
- Definition: standardized distance of close from 20-bar mean.
- Formula: (close_t - mean_20) / std_20.
- Interpretation: indicates stretch versus local equilibrium.
- Stronger use cases: mean reversion and recenter signals.
- Failure modes: extreme trends can stay stretched for longer than expected.
- Downstream usage: zscore_recenter signal and regime sanity checks.

### 2. Trend structure
#### ema_spread_8_21
- Definition: normalized spread between fast and slow EMA.
- Formula: (EMA_8 - EMA_21) / close_t.
- Interpretation: compact representation of local trend alignment.
- Stronger use cases: trend continuation, directional state scoring.
- Failure modes: weak in sideways markets; sensitive to whipsaws.
- Downstream usage: trend filters and trend-family signals.

### 3. Participation and activity
#### rel_volume_20
- Definition: current volume relative to 20-bar mean volume.
- Formula: volume_t / mean(volume_20).
- Interpretation: measures whether current move is supported by activity.
- Stronger use cases: breakout validation and conviction checks.
- Failure modes: can understate conviction in assets with naturally bursty flow.
- Downstream usage: breakout gating, participation filters.

### 4. Volatility and compression
#### volatility_20
- Definition: standard deviation of closes over 20 bars, normalized by mean close.
- Formula: std(close_20) / mean(close_20).
- Interpretation: compact estimate of local realized dispersion.
- Stronger use cases: regime labeling, squeeze detection, risk scaling.
- Failure modes: uses close-only dispersion; may miss intrabar instability.
- Downstream usage: regime_engine and volatility-aware signal gating.

## Expansion roadmap
- Add intrabar range family: true range, ATR, wick imbalance, close-location value.
- Add market microstructure family: spread, depth imbalance, trade aggressor imbalance.
- Add cross-context family: beta-to-benchmark, basis, funding context, correlation stress.
- Add event-state family: volatility shocks, session boundaries, breakout exhaustion.

## Dependency map
- Bars and micro-updates feed factor calculation.
- Factors feed indicator interpretation.
- Factors and indicators jointly feed signal templates.
- Signals feed strategy thesis generation.
