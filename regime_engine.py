from __future__ import annotations

from typing import Dict, Any


def classify_regime(factors: Dict[str, float], indicators: Dict[str, float]) -> Dict[str, Any]:
    ret_5 = factors.get('ret_5', 0.0)
    vol_20 = factors.get('volatility_20', 0.0)
    macd = indicators.get('MACD', 0.0)
    bb_width = indicators.get('BollingerWidth', 0.0)
    z = indicators.get('ZScore_Close', 0.0)

    if vol_20 > 0.03 and abs(ret_5) > 0.015:
        regime = 'high_volatility'
        confidence = 0.72
    elif bb_width < 0.025 and abs(z) < 0.5 and vol_20 < 0.015:
        regime = 'range_chop'
        confidence = 0.64
    elif macd > 0 and ret_5 > 0.003:
        regime = 'uptrend'
        confidence = 0.68
    elif macd < 0 and ret_5 < -0.003:
        regime = 'downtrend'
        confidence = 0.68
    elif vol_20 > 0.01 and abs(ret_5) < 0.005:
        regime = 'transition_ambiguous'
        confidence = 0.55
    else:
        regime = 'transition_ambiguous'
        confidence = 0.51

    tradable = regime in {'uptrend', 'downtrend', 'range_chop'}

    if regime == 'uptrend':
        allowed = ['continuation', 'breakout', 'order_flow',
                   'cross_asset', 'divergence', 'mean_reversion']
    elif regime == 'downtrend':
        allowed = ['continuation', 'breakout', 'order_flow',
                   'cross_asset', 'divergence', 'mean_reversion']
    elif regime == 'range_chop':
        allowed = ['mean_reversion', 'divergence']
    else:
        allowed = []

    return {
        'regime': regime,
        'confidence': confidence,
        'tradable': tradable,
        'allowed_signal_families': allowed,
        'why': {
            'ret_5': ret_5,
            'volatility_20': vol_20,
            'macd': macd,
            'bollinger_width': bb_width,
            'zscore_close': z,
        },
    }
