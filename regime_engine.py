from __future__ import annotations

from typing import Dict, Any


def classify_regime(factors: Dict[str, float], indicators: Dict[str, float]) -> Dict[str, Any]:
    """
    Classify the market state using a 3x3 matrix:
    Trend: BULL, BEAR, SIDEWAYS
    Volatility: LOW, NORMAL, HIGH
    
    Maps combinations to 6 Strategy Groups:
    - Group A (🟢 Bull Low-Normal Vol): 'bull_low_normal_vol'
    - Group B (🟠 Bull High Vol): 'bull_high_vol'
    - Group C (🟣 Sideways High Vol): 'sideways_high_vol'
    - Group D (🔴 Bear High Vol): 'bear_high_vol'
    - Group E (🟤 Bear Low-Normal Vol): 'bear_low_normal_vol'
    - Group F (⚪ Sideways Low-Normal Vol): 'sideways_low_normal_vol'
    """
    vol_20 = factors.get('volatility_20', 0.0)
    ema_spread = factors.get('ema_spread_8_21', 0.0)
    adx = indicators.get('adx_14', 0.0)
    
    # 1. Volatility classification
    if vol_20 < 0.012:
        vol_state = 'low_vol'
    elif vol_20 < 0.025:
        vol_state = 'normal_vol'
    else:
        vol_state = 'high_vol'

    # 2. Trend classification (using ema_spread and ADX trend strength)
    if ema_spread > 0.002:
        trend_state = 'bull'
    elif ema_spread < -0.002:
        trend_state = 'bear'
    else:
        trend_state = 'sideways'

    # 3. 3x3 Matrix mapping to Groups A-F
    if trend_state == 'bull':
        if vol_state == 'high_vol':
            regime = 'bull_high_vol'
            group = 'Group B'
            confidence = 0.74
            allowed_strategies = ['high_vol_breakout', 'momentum_chasing', 'vwap_reversion_fade']
            allowed_families = ['breakout', 'continuation', 'mean_reversion']
        else:
            regime = 'bull_low_normal_vol'
            group = 'Group A'
            confidence = 0.82
            allowed_strategies = ['macd_trend_continuation', 'ema_pullback_buy', 'obv_accumulation_breakout']
            allowed_families = ['continuation']
    elif trend_state == 'bear':
        if vol_state == 'high_vol':
            regime = 'bear_high_vol'
            group = 'Group D'
            confidence = 0.74
            allowed_strategies = ['high_vol_breakdown', 'short_momentum_chase', 'oversold_bounce']
            allowed_families = ['breakout', 'continuation', 'mean_reversion']
        else:
            regime = 'bear_low_normal_vol'
            group = 'Group E'
            confidence = 0.82
            allowed_strategies = ['bearish_trend_continuation', 'ema_pullback_sell', 'obv_distribution_breakdown']
            allowed_families = ['continuation']
    else:  # sideways
        if vol_state == 'high_vol':
            regime = 'sideways_high_vol'
            group = 'Group C'
            confidence = 0.68
            allowed_strategies = ['range_boundary_fade', 'liquidity_sweep_hunt', 'hft_order_flow_momentum']
            allowed_families = ['mean_reversion', 'order_flow']
        else:
            regime = 'sideways_low_normal_vol'
            group = 'Group F'
            confidence = 0.65
            allowed_strategies = ['mean_reversion_squeeze', 'funding_reversion', 'oi_reversal']
            allowed_families = ['mean_reversion', 'funding_reversion', 'oi_reversal']

    # Keep backward compatibility: check if the regime is tradable
    tradable = True
    trade_tier = 'full' if vol_state == 'normal_vol' else 'selective' if vol_state == 'high_vol' else 'cautious'

    return {
        'regime': regime,
        'group': group,
        'trend_state': trend_state,
        'vol_state': vol_state,
        'confidence': confidence,
        'tradable': tradable,
        'trade_tier': trade_tier,
        'allowed_signal_families': allowed_families,
        'allowed_strategies': allowed_strategies,
        'why': {
            'volatility_20': vol_20,
            'ema_spread_8_21': ema_spread,
            'adx_14': adx,
        },
    }

