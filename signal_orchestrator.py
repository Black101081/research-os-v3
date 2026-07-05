from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any
from indicator_keys import (
    BOLLINGER_SQUEEZE_THRESHOLD,
    ZSCORE_ENTRY_LONG_THRESHOLD,
)

TOOLKIT_PATH = Path(__file__).resolve().parent.parent / 'signal_toolkit_v2' / 'signal_toolkit_v2.json'
SIGNALS = json.loads(TOOLKIT_PATH.read_text()) if TOOLKIT_PATH.exists() else []
SIGNAL_INDEX = {s['signal_name']: s for s in SIGNALS}

SUPPORTED = ['bollinger_squeeze_breakout', 'zscore_recenter', 'macd_trend_continuation']


def _regime_allowed(template: Dict[str, Any], regime_state: Dict[str, Any]) -> bool:
    regime = regime_state.get('regime')
    preferred = template.get('preferred_regimes', [])
    avoid = template.get('avoid_regimes', [])
    if regime in avoid:
        return False
    if preferred and regime not in preferred:
        return False
    return True


def evaluate_supported_signals(symbol: str, factors: Dict[str, float], indicators: Dict[str, float], regime_state: Dict[str, Any], last_close: float | None, prev_bollinger_width: float | None = None) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name in SUPPORTED:
        spec = SIGNAL_INDEX.get(name, {})
        template = spec.get('signal_template', {})
        regime_ok = _regime_allowed(template, regime_state)
        if name == 'bollinger_squeeze_breakout':
            was_squeezing = (prev_bollinger_width is not None) and (prev_bollinger_width <= BOLLINGER_SQUEEZE_THRESHOLD)
            breakout = (last_close is not None) and last_close > indicators.get('BBANDS_upper', float('inf'))
            rel_vol_ok = indicators.get('RelativeVolume', 0.0) >= 1.0
            active = bool(was_squeezing and breakout and rel_vol_ok and regime_ok and regime_state.get('tradable', False))
            why = {
                'squeeze': was_squeezing,
                'was_squeezing': was_squeezing,
                'prev_bollinger_width': prev_bollinger_width,
                'breakout': breakout,
                'relative_volume': rel_vol_ok,
                'regime_ok': regime_ok,
            }
        elif name == 'zscore_recenter':
            z = indicators.get('ZScore_Close', 0.0)
            active = bool(z <= ZSCORE_ENTRY_LONG_THRESHOLD and regime_ok and regime_state.get('tradable', False))
            why = {'zscore': z, 'zscore_entry_condition': z <= ZSCORE_ENTRY_LONG_THRESHOLD, 'regime_ok': regime_ok}
        else:
            macd = indicators.get('MACD', 0.0)
            macd_signal = indicators.get('MACD_signal', 0.0)
            active = bool(macd > macd_signal and macd > 0 and regime_ok and regime_state.get('tradable', False))
            why = {'macd': macd, 'macd_signal': macd_signal, 'macd_above_signal': macd > macd_signal, 'regime_ok': regime_ok}
        out[name] = {
            'active': active,
            'why': why,
            'template_family': spec.get('signal_family', 'unknown'),
            'preferred_regimes': template.get('preferred_regimes', []),
            'avoid_regimes': template.get('avoid_regimes', []),
            'thesis': spec.get('signal_thesis', {}).get('what_edge_it_targets'),
        }
    return out
