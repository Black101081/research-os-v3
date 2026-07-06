from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List, Optional
import time

from indicator_keys import BOLLINGER_SQUEEZE_THRESHOLD
from promoted_signal_bridge import PromotedSignalBridge
from multi_tf_state import MultiTFSymbolState, TFState, TFBar
from collections import deque

# Import the new structures
from signal_models import SignalResult, SignalBatch
from signal_library import (
    evaluate_all_signals,
    DIRECTION_BOTH, DIRECTION_LONG, DIRECTION_SHORT,
    FAMILY_BREAKOUT, FAMILY_CONTINUATION, FAMILY_DIVERGENCE,
    FAMILY_FUNDING_REVERSION, FAMILY_MEAN_REVERSION,
    FAMILY_OI_REVERSAL, FAMILY_ORDER_FLOW, FAMILY_VOLATILITY_EVENT,
)

# Path to template library
TEMPLATE_LIBRARY_PATH = Path(__file__).resolve().parent / 'signal_template_library_v1.json'

_catalog_cache = None
_catalog_cache_time = 0.0
CATALOG_CACHE_TTL = 30.0

def _load_catalog():
    global _catalog_cache, _catalog_cache_time
    now = time.time()
    if _catalog_cache is None or now - _catalog_cache_time > CATALOG_CACHE_TTL:
        if TEMPLATE_LIBRARY_PATH.exists():
            try:
                data = json.loads(TEMPLATE_LIBRARY_PATH.read_text(encoding='utf-8'))
            except Exception:
                data = {}
        else:
            data = {}
        templates = data.get('template_families', [])
        templates_by_family = {t['family']: t for t in templates}
        catalog = data.get('signal_catalog', [])
        catalog_by_id = {s['signal_id']: s for s in catalog}
        _catalog_cache = (templates_by_family, catalog, catalog_by_id)
        _catalog_cache_time = now
    return _catalog_cache

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

# Best available timeframes for each signal family
BEST_TFS = {
    FAMILY_CONTINUATION:      ["1h", "15m", "5m", "1m"],
    FAMILY_DIVERGENCE:        ["1h", "15m", "5m", "1m"],
    FAMILY_BREAKOUT:          ["15m", "5m", "1m"],
    FAMILY_MEAN_REVERSION:    ["1h", "15m", "1m"],
    FAMILY_ORDER_FLOW:        ["5m", "1m"],
    FAMILY_VOLATILITY_EVENT:  ["5m", "1m"],
    FAMILY_FUNDING_REVERSION: ["15m", "5m", "1m"],
    FAMILY_OI_REVERSAL:       ["15m", "5m", "1m"],
}

def evaluate_supported_signals(
    symbol: str,
    factors: Dict[str, float],
    indicators: Dict[str, float],
    regime_state: Dict[str, Any],
    last_close: float | None,
    prev_bollinger_width: float | None,
    sym_state: Optional[MultiTFSymbolState] = None
) -> Dict[str, Dict[str, Any]]:

    # 1. Load promoted alphas or catalog signals (legacy fallback)
    promoted = bridge.load_promoted_alphas()
    out: Dict[str, Dict[str, Any]] = {}
    context = {**factors, **indicators}
    templates_by_family, catalog, catalog_by_id = _load_catalog()

    if promoted:
        for alpha in promoted:
            name = alpha.get('alpha_name', alpha['alpha_id'])
            trigger_expr = alpha.get('trigger_definition') or alpha.get('signal_expression') or ''
            confirm_expr = alpha.get('confirmation_definition') or ''
            invalidate_expr = alpha.get('invalidation_definition') or ''
            
            triggered = safe_eval_expression(trigger_expr, context)
            confirmed = safe_eval_expression(confirm_expr, context) if confirm_expr else True
            invalidated = safe_eval_expression(invalidate_expr, context) if invalidate_expr else False
            
            preferred = alpha.get('preferred_regimes') or alpha.get('regime_scope') or []
            avoid = alpha.get('avoid_regimes', [])
            current_regime = regime_state.get('regime')
            if avoid and current_regime in avoid:
                regime_ok = False
            elif preferred and current_regime not in preferred:
                regime_ok = False
            else:
                regime_ok = True
            
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
        for sig in catalog:
            name = sig['signal_id']
            family = sig.get('family', 'unknown')
            template = templates_by_family.get(family, {})
            regime_ok = _regime_allowed(sig, regime_state)
            
            trigger_expr = sig.get('trigger_definition', '')
            confirm_expr = sig.get('confirmation_definition', '')
            invalidate_expr = sig.get('invalidation_definition', '')
            
            triggered = safe_eval_expression(trigger_expr, context)
            confirmed = safe_eval_expression(confirm_expr, context) if confirm_expr else True
            invalidated = safe_eval_expression(invalidate_expr, context) if invalidate_expr else False
            
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

    # 2. Upgraded pure signal library evaluation
    # Build or use sym_state
    if sym_state is None:
        # Cannot build meaningful sym_state without real bar history.
        # Skip signal library evaluation entirely to avoid false negatives
        # from flat mock bars (ATR=0, MACD=0 kill every signal).
        pass
    
    if sym_state is not None:
        # Asset role mapping
        asset_role = "anchor" if symbol == "BTC" else "major"

        # Evaluate each of the 8 signal families
        families_mapping = {
            FAMILY_CONTINUATION:      "signal_macd_continuation",
            FAMILY_DIVERGENCE:        "signal_rsi_divergence",
            FAMILY_BREAKOUT:          "signal_bb_squeeze_breakout",
            FAMILY_MEAN_REVERSION:    "signal_mean_reversion",
            FAMILY_ORDER_FLOW:        "signal_order_flow_imbalance",
            FAMILY_VOLATILITY_EVENT:  "signal_volatility_event",
            FAMILY_FUNDING_REVERSION: "signal_funding_reversion",
            FAMILY_OI_REVERSAL:       "signal_oi_reversal",
        }

        # Call evaluate_all_signals ONCE per timeframe, cache results
        # Group families by their best available TF first
        tf_to_families: dict = {}
        for family, sig_name in families_mapping.items():
            tf_to_use = "1m"
            for t in BEST_TFS.get(family, ["1m"]):
                if t in sym_state.tf_states:
                    tf_to_use = t
                    break
            tf_to_families.setdefault(tf_to_use, []).append((family, sig_name))

        # One batch call per unique TF
        tf_batch_cache: dict = {}
        for tf_to_use, family_pairs in tf_to_families.items():
            batch = evaluate_all_signals(sym_state, tf_to_use, asset_role)
            results_by_family = {r.family: r for r in batch.results}
            tf_batch_cache[tf_to_use] = results_by_family

        for family, sig_name in families_mapping.items():
            tf_to_use = "1m"
            for t in BEST_TFS.get(family, ["1m"]):
                if t in sym_state.tf_states:
                    tf_to_use = t
                    break
            sig_res = tf_batch_cache.get(tf_to_use, {}).get(family)

            if sig_res:
                res_dict = sig_res.to_dict()
                res_dict['active'] = sig_res.fired
                res_dict['triggered'] = sig_res.fired
                res_dict['confirmed'] = sig_res.fired
                res_dict['invalidated'] = False if sig_res.fired else (True if sig_res.invalidation_reason else False)
                res_dict['confirmation_score'] = sig_res.confidence_score
                res_dict['invalidation_score'] = 1.0 - sig_res.confidence_score if sig_res.invalidation_reason else 0.0
                res_dict['template_family'] = sig_res.family
                res_dict['why'] = {
                    'triggered': sig_res.fired,
                    'confirmed': sig_res.fired,
                    'invalidated': res_dict['invalidated'],
                    'invalidation_reason': sig_res.invalidation_reason,
                }
                out[sig_name] = res_dict

        # Post-filtering for allowed_signal_families
        allowed_families = regime_state.get('allowed_signal_families', [])
        for signal_name, signal_result in out.items():
            family = signal_result.get('template_family', '')
            if not family or family == 'unknown':
                if 'mean_reversion' in signal_name or 'zscore' in signal_name:
                    family = 'mean_reversion'
                elif 'divergence' in signal_name:
                    family = 'divergence'
                elif 'macd' in signal_name or 'continuation' in signal_name:
                    family = 'continuation'
                elif 'flow' in signal_name or 'imbalance' in signal_name:
                    family = 'order_flow'
                elif 'breakout' in signal_name:
                    family = 'breakout'
                else:
                    family = 'continuation'
                signal_result['template_family'] = family

            if allowed_families and family not in allowed_families:
                signal_result['active'] = False
                signal_result['invalidated'] = True
                signal_result['invalidation_reason'] = f'regime_family_blocked:{regime_state.get("regime","unknown")}'
                signal_result['why']['invalidated'] = True
                signal_result['why']['invalidation_reason'] = signal_result['invalidation_reason']

    return out


class SignalOrchestrator:
    def __init__(self, mtf_engine=None, paper_broker=None):
        from quality_gate import QualityGate
        from quality_gate_models import QualityGateConfig
        self._mtf = mtf_engine
        self._paper_broker = paper_broker
        self._quality_gate = QualityGate(
            config=QualityGateConfig(),
            mtf_engine=self._mtf,
        )
        import globals as _globals
        _globals.quality_gate = self._quality_gate

    def _emit_signal(self, signal: "SignalResult") -> None:
        """
        Run signal through QualityGate before forwarding to paper_broker.
        Only QualifiedSignal objects reach the broker.
        GateRejection objects are logged and discarded.
        """
        import logging
        log = logging.getLogger(__name__)

        from quality_gate_models import QualifiedSignal
        result = self._quality_gate.evaluate(signal)
        if isinstance(result, QualifiedSignal):
            # Forward QualifiedSignal sang PaperBroker để mở position
            import globals as _globals
            _globals.broker.on_qualified_signal(result)
            _globals.quality_gate = self._quality_gate

    def on_trade_closed(self, signal_id: str, pnl_usd: float = 0.0) -> None:
        """Called by paper_broker when a trade closes."""
        self._quality_gate.on_signal_closed(signal_id)
        # Update account equity
        current_equity = self._quality_gate._cfg.sizing.account_equity
        self._quality_gate.update_account_equity(current_equity + pnl_usd)
