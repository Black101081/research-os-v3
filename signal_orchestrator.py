from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List
from indicator_keys import BOLLINGER_SQUEEZE_THRESHOLD
from promoted_signal_bridge import PromotedSignalBridge

# Load template families from catalog
TEMPLATE_LIBRARY_PATH = Path(__file__).resolve().parent / 'signal_template_library_v1.json'
LIBRARY_DATA = json.loads(TEMPLATE_LIBRARY_PATH.read_text(encoding='utf-8')) if TEMPLATE_LIBRARY_PATH.exists() else {}
TEMPLATES = LIBRARY_DATA.get('template_families', [])
TEMPLATE_BY_FAMILY = {t['family']: t for t in TEMPLATES}
CATALOG = LIBRARY_DATA.get('signal_catalog', [])
CATALOG_BY_ID = {s['signal_id']: s for s in CATALOG}

# Initialize bridge
bridge = PromotedSignalBridge()

SUPPORTED = ['bollinger_squeeze_breakout', 'zscore_recenter', 'macd_trend_continuation']


def safe_eval_expression(expr: str, context: Dict[str, float]) -> bool:
    safe_dict = {k: float(v) for k, v in context.items() if isinstance(v, (int, float))}
    safe_dict['True'] = True
    safe_dict['False'] = False
    safe_dict['abs'] = abs
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.<>=!+-*/() \t")
    if not all(c in allowed_chars for c in expr):
        return False
    try:
        return bool(eval(expr, {"__builtins__": None}, safe_dict))
    except Exception:
        return False


def compute_expr_score(expr: str, context: Dict[str, float], is_invalidation: bool = False) -> float:
    if not expr:
        return 0.0 if is_invalidation else 1.0
    import re
    parts = re.split(r'\s+(?:and|or)\s+', expr)
    if not parts:
        return 0.0 if is_invalidation else 1.0
    passed = 0
    total = 0
    for p in parts:
        p = p.strip()
        if not p:
            continue
        total += 1
        if safe_eval_expression(p, context):
            passed += 1
    return float(passed) / total if total > 0 else (0.0 if is_invalidation else 1.0)


def _regime_allowed(sig: Dict[str, Any], regime_state: Dict[str, Any]) -> bool:
    regime = regime_state.get('regime')
    preferred = sig.get('preferred_regimes') or sig.get('default_regime_scope', [])
    avoid = sig.get('avoid_regimes', [])
    if regime in avoid:
        return False
    if preferred and regime not in preferred:
        return False
    return True


def evaluate_supported_signals(symbol: str, factors: Dict[str, float], indicators: Dict[str, float], regime_state: Dict[str, Any], last_close: float | None, prev_bollinger_width: float | None) -> Dict[str, Dict[str, Any]]:
    # 1. Try to load promoted alphas
    promoted = bridge.load_promoted_alphas()
    
    out: Dict[str, Dict[str, Any]] = {}
    context = {**factors, **indicators}
    
    if promoted:
        for alpha in promoted:
            name = alpha.get('alpha_name', alpha['alpha_id'])
            
            trigger_expr = alpha.get('trigger_definition') or alpha.get('signal_expression') or ''
            confirm_expr = alpha.get('confirmation_definition') or ''
            invalidate_expr = alpha.get('invalidation_definition') or ''
            
            triggered = safe_eval_expression(trigger_expr, context)
            confirmed = safe_eval_expression(confirm_expr, context) if confirm_expr else True
            invalidated = safe_eval_expression(invalidate_expr, context) if invalidate_expr else False
            
            regime_ok = (regime_state.get('regime') in alpha.get('regime_scope', []))
            active = bool(triggered and confirmed and not invalidated and regime_ok and regime_state.get('tradable', False))
            
            confirmation_score = compute_expr_score(confirm_expr, context, is_invalidation=False)
            invalidation_score = compute_expr_score(invalidate_expr, context, is_invalidation=True)
            
            why = {
                'triggered': triggered,
                'confirmed': confirmed,
                'invalidated': invalidated,
                'regime_ok': regime_ok,
                'trigger_expression': trigger_expr,
                'confirmation_expression': confirm_expr,
                'invalidation_expression': invalidate_expr,
                'alpha_id': alpha['alpha_id'],
            }
            
            out[name] = {
                'triggered': triggered,
                'confirmed': confirmed,
                'invalidated': invalidated,
                'confirmation_score': confirmation_score,
                'invalidation_score': invalidation_score,
                'active': active,
                'why': why,
                'template_family': alpha.get('signal_template_family', 'unknown'),
                'preferred_regimes': alpha.get('regime_scope', []),
                'avoid_regimes': [],
                'direction': alpha.get('direction', 'both'),
                'thesis': alpha.get('thesis_summary', 'Promoted Alpha'),
                'entry_logic_summary': alpha.get('entry_logic_summary', 'Custom Promoted Entry'),
                'confirmation_summary': alpha.get('confirmation_summary', 'Custom Promoted Confirmation'),
                'invalidation_summary': alpha.get('invalidation_summary', 'Custom Promoted Invalidation'),
                'quality_tier': alpha.get('quality_tier', 'A'),
            }
    else:
        # Fallback to catalog signals
        for sig in CATALOG:
            name = sig['signal_id']
            family = sig.get('family', 'unknown')
            template = TEMPLATE_BY_FAMILY.get(family, {})
            regime_ok = _regime_allowed(sig, regime_state)
            
            trigger_expr = sig.get('trigger_definition', '')
            confirm_expr = sig.get('confirmation_definition', '')
            invalidate_expr = sig.get('invalidation_definition', '')
            
            triggered = safe_eval_expression(trigger_expr, context)
            confirmed = safe_eval_expression(confirm_expr, context) if confirm_expr else True
            invalidated = safe_eval_expression(invalidate_expr, context) if invalidate_expr else False
            
            # Special legacy evaluation for default bollinger_squeeze_breakout if needed
            if name == 'bollinger_squeeze_breakout' and prev_bollinger_width is not None:
                was_squeezing = prev_bollinger_width <= BOLLINGER_SQUEEZE_THRESHOLD
                breakout = (last_close is not None) and (last_close > indicators.get('BBANDS_upper', float('inf')) or last_close < indicators.get('BBANDS_lower', float('-inf')))
                triggered = was_squeezing and breakout
                
            active = bool(triggered and confirmed and not invalidated and regime_ok and regime_state.get('tradable', False))
            
            confirmation_score = compute_expr_score(confirm_expr, context, is_invalidation=False)
            invalidation_score = compute_expr_score(invalidate_expr, context, is_invalidation=True)
            
            why = {
                'triggered': triggered,
                'confirmed': confirmed,
                'invalidated': invalidated,
                'regime_ok': regime_ok,
                'trigger_expression': trigger_expr,
                'confirmation_expression': confirm_expr,
                'invalidation_expression': invalidate_expr,
            }
            # Preserve special fields for default 3 signals if expected by existing tests
            if name == 'bollinger_squeeze_breakout':
                why['squeeze'] = (prev_bollinger_width is not None) and (prev_bollinger_width <= BOLLINGER_SQUEEZE_THRESHOLD)
                why['breakout'] = (last_close is not None) and last_close > indicators.get('BBANDS_upper', float('inf'))
                why['relative_volume'] = indicators.get('RelativeVolume', 0.0) >= 1.0
            elif name == 'zscore_recenter':
                why['zscore'] = indicators.get('ZScore_Close', 0.0)
                why['zscore_entry_condition'] = why['zscore'] <= -1.5
            elif name == 'macd_trend_continuation':
                why['macd'] = indicators.get('MACD', 0.0)
                why['macd_signal'] = indicators.get('MACD_signal', 0.0)
                why['macd_above_signal'] = why['macd'] > why['macd_signal']
            
            out[name] = {
                'triggered': triggered,
                'confirmed': confirmed,
                'invalidated': invalidated,
                'confirmation_score': confirmation_score,
                'invalidation_score': invalidation_score,
                'active': active,
                'why': why,
                'template_family': family,
                'preferred_regimes': sig.get('preferred_regimes', []),
                'avoid_regimes': sig.get('avoid_regimes', []),
                'direction': sig.get('direction', 'both'),
                'thesis': sig.get('thesis_summary'),
                'entry_logic_summary': sig.get('entry_logic_summary'),
                'confirmation_summary': sig.get('confirmation_summary'),
                'invalidation_summary': sig.get('invalidation_summary'),
                'quality_tier': sig.get('quality_tier', 'A'),
            }
            
    return out
