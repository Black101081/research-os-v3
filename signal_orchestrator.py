from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List
from indicator_keys import BOLLINGER_SQUEEZE_THRESHOLD
from promoted_signal_bridge import PromotedSignalBridge

# Load template families from catalog
TEMPLATE_LIBRARY_PATH = Path(__file__).resolve().parent / 'signal_template_library_v1.json'
TEMPLATES = json.loads(TEMPLATE_LIBRARY_PATH.read_text(encoding='utf-8')).get('template_families', []) if TEMPLATE_LIBRARY_PATH.exists() else []
TEMPLATE_BY_FAMILY = {t['family']: t for t in TEMPLATES}

# Initialize bridge
bridge = PromotedSignalBridge()

SUPPORTED = ['bollinger_squeeze_breakout', 'zscore_recenter', 'macd_trend_continuation']


def safe_eval_expression(expr: str, context: Dict[str, float]) -> bool:
    safe_dict = {k: float(v) for k, v in context.items() if isinstance(v, (int, float))}
    safe_dict['True'] = True
    safe_dict['False'] = False
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.<>=!+-*/() \t")
    if not all(c in allowed_chars for c in expr):
        return False
    try:
        return bool(eval(expr, {"__builtins__": None}, safe_dict))
    except Exception:
        return False


def _regime_allowed(template: Dict[str, Any], regime_state: Dict[str, Any]) -> bool:
    regime = regime_state.get('regime')
    preferred = template.get('preferred_regimes') or template.get('default_regime_scope', [])
    avoid = template.get('avoid_regimes', [])
    if regime in avoid:
        return False
    if preferred and regime not in preferred:
        return False
    return True


def evaluate_supported_signals(symbol: str, factors: Dict[str, float], indicators: Dict[str, float], regime_state: Dict[str, Any], last_close: float | None, prev_bollinger_width: float | None) -> Dict[str, Dict[str, Any]]:
    # 1. Try to load promoted alphas
    promoted = bridge.load_promoted_alphas()
    
    out: Dict[str, Dict[str, Any]] = {}
    
    if promoted:
        context = {**factors, **indicators}
        for alpha in promoted:
            name = alpha.get('alpha_name', alpha['alpha_id'])
            expr = alpha.get('signal_expression', '')
            family = alpha.get('signal_template_family', 'unknown')
            
            regime_ok = (regime_state.get('regime') in alpha.get('regime_scope', []))
            expr_val = safe_eval_expression(expr, context)
            active = bool(expr_val and regime_ok and regime_state.get('tradable', False))
            
            why = {
                'expression': expr,
                'expr_val': expr_val,
                'regime_ok': regime_ok,
                'alpha_id': alpha['alpha_id'],
            }
            
            out[name] = {
                'active': active,
                'why': why,
                'template_family': family,
                'preferred_regimes': alpha.get('regime_scope', []),
                'avoid_regimes': [],
                'thesis': alpha.get('thesis_summary'),
            }
    else:
        # Fallback to default 3 signals
        for name in SUPPORTED:
            family_map = {
                'bollinger_squeeze_breakout': 'breakout',
                'zscore_recenter': 'mean_reversion',
                'macd_trend_continuation': 'continuation'
            }
            family = family_map.get(name, 'unknown')
            template = TEMPLATE_BY_FAMILY.get(family, {})
            regime_ok = _regime_allowed(template, regime_state)
            
            if name == 'bollinger_squeeze_breakout':
                was_squeezing = (prev_bollinger_width is not None) and (prev_bollinger_width <= BOLLINGER_SQUEEZE_THRESHOLD)
                breakout = (last_close is not None) and last_close > indicators.get('BBANDS_upper', float('inf'))
                rel_vol_ok = indicators.get('RelativeVolume', 0.0) >= 1.0
                active = bool(was_squeezing and breakout and rel_vol_ok and regime_ok and regime_state.get('tradable', False))
                why = {'squeeze': was_squeezing, 'breakout': breakout, 'relative_volume': rel_vol_ok, 'regime_ok': regime_ok}
            elif name == 'zscore_recenter':
                z = indicators.get('ZScore_Close', 0.0)
                active = bool(z <= -1.5 and regime_ok and regime_state.get('tradable', False))
                why = {'zscore': z, 'zscore_entry_condition': z <= -1.5, 'regime_ok': regime_ok}
            else:
                macd = indicators.get('MACD', 0.0)
                macd_signal = indicators.get('MACD_signal', 0.0)
                active = bool(macd > macd_signal and macd > 0 and regime_ok and regime_state.get('tradable', False))
                why = {'macd': macd, 'macd_signal': macd_signal, 'macd_above_signal': macd > macd_signal, 'regime_ok': regime_ok}
            
            out[name] = {
                'active': active,
                'why': why,
                'template_family': family,
                'preferred_regimes': template.get('default_regime_scope', []),
                'avoid_regimes': [],
                'thesis': template.get('thesis_template', {}).get('what_edge_it_targets'),
            }
            
    return out
