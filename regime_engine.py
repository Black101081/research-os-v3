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
    elif macd > 0 and ret_5 > 0:
        regime = 'uptrend'
        confidence = 0.68
    elif macd < 0 and ret_5 < 0:
        regime = 'downtrend'
        confidence = 0.68
    elif bb_width < 0.03 and abs(z) < 0.75:
        regime = 'range_chop'
        confidence = 0.64
    else:
        regime = 'transition_ambiguous'
        confidence = 0.51

    tradable = regime in {'uptrend', 'downtrend', 'range_chop'}
    return {
        'regime': regime,
        'confidence': confidence,
        'tradable': tradable,
        'why': {
            'ret_5': ret_5,
            'volatility_20': vol_20,
            'macd': macd,
            'bollinger_width': bb_width,
            'zscore_close': z,
        },
    }
