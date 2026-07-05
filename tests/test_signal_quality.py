from __future__ import annotations

import pytest
import json
from pathlib import Path
from signal_generator import SignalGenerator
from signal_orchestrator import evaluate_supported_signals, safe_eval_expression, compute_expr_score
from realtime_engine import ResearchEngine, SymbolState

# Load catalog
TEMPLATE_LIBRARY_PATH = Path(__file__).resolve().parents[1] / 'signal_template_library_v1.json'
with open(TEMPLATE_LIBRARY_PATH, 'r', encoding='utf-8') as f:
    LIBRARY_DATA = json.load(f)

def test_catalog_quality_fields():
    """Verify that every signal in the catalog has trigger, confirmation, and invalidation definitions."""
    catalog = LIBRARY_DATA.get('signal_catalog', [])
    assert len(catalog) > 0
    
    for sig in catalog:
        assert 'trigger_definition' in sig, f"Missing trigger_definition in {sig['signal_id']}"
        assert 'confirmation_definition' in sig, f"Missing confirmation_definition in {sig['signal_id']}"
        assert 'invalidation_definition' in sig, f"Missing invalidation_definition in {sig['signal_id']}"
        
        assert sig['trigger_definition'] is not None
        assert sig['confirmation_definition'] is not None
        assert sig['invalidation_definition'] is not None
        
        assert 'thesis_summary' in sig
        assert 'entry_logic_summary' in sig
        assert 'confirmation_summary' in sig
        assert 'invalidation_summary' in sig
        assert 'quality_tier' in sig
        assert 'min_confirmation_score' in sig
        assert 'min_invalidation_score' in sig
        # assert 'execution_sensitivity_summary' in sig

def test_generator_upgraded_output():
    """Verify that the generator produces candidates with full definitions and metadata."""
    dummy_factors = {
        "families": [
            {
                "family": "core",
                "factors": [
                    {"factor_id": "BollingerWidth"},
                    {"factor_id": "live_ret_from_last_close"},
                    {"factor_id": "zscore_close_20"},
                    {"factor_id": "micro_volatility_20"},
                    {"factor_id": "MACD"},
                    {"factor_id": "MACD_signal"},
                    {"factor_id": "ema_spread_8_21"},
                    {"factor_id": "spread_bps"},
                    {"factor_id": "tick_ret_5"},
                    {"factor_id": "trade_flow_imbalance_20"},
                    {"factor_id": "bb_pct_b"},
                    {"factor_id": "rsi_14"},
                    {"factor_id": "price_vs_sma20"},
                    {"factor_id": "volatility_ratio_5_20"},
                    {"factor_id": "atr_pct_14"},
                    {"factor_id": "momentum_divergence"},
                    {"factor_id": "trade_flow_imbalance_50"},
                    {"factor_id": "large_trade_ratio"},
                    {"factor_id": "btc_ret_1"},
                    {"factor_id": "market_correlation_20"}
                ]
            }
        ]
    }
    
    gen = SignalGenerator(dummy_factors, LIBRARY_DATA)
    candidates = gen.generate_candidates()
    assert len(candidates) > 0
    
    for c in candidates:
        assert c['trigger_definition'] is not None
        assert c['confirmation_definition'] is not None
        assert c['invalidation_definition'] is not None
        assert c['thesis_summary'] is not None
        assert c['entry_logic_summary'] is not None
        assert c['confirmation_summary'] is not None
        assert c['invalidation_summary'] is not None
        assert c['quality_tier'] in ['A', 'B']
        assert c['min_confirmation_score'] in [0.5, 0.6]
        assert c['min_invalidation_score'] == 0.5
        assert c['execution_sensitivity_summary'] is not None

def test_orchestrator_evaluation():
    """Test 3-layer orchestrator evaluation under various indicator conditions."""
    factors = {"live_ret_from_last_close": 0.002}
    indicators = {
        "BollingerWidth": 0.06,
        "volatility_ratio_5_20": 1.2,
        "RelativeVolume": 1.5,
        "TradeFlowImbalance": 0.35,
        "rsi_14": 45,
        "ZScore_Close": 0.5,
        "SpreadBps": 2.0,
        "BBANDS_upper": 60000.0,
        "BBANDS_lower": 50000.0
    }
    regime_state = {
        "regime": "uptrend",
        "tradable": True
    }
    
    # Test bollinger_squeeze_breakout (which has triggers active)
    res = evaluate_supported_signals("BTC", factors, indicators, regime_state, last_close=62000.0, prev_bollinger_width=0.08)
    assert 'bollinger_squeeze_breakout' in res
    sig = res['bollinger_squeeze_breakout']
    
    assert sig['triggered'] is True
    assert sig['confirmed'] is True
    assert sig['invalidated'] is False
    assert sig['active'] is True
    assert sig['confirmation_score'] == 1.0
    assert sig['invalidation_score'] == 0.0
    
    # Now let's trigger invalidation by expanding spread
    indicators["SpreadBps"] = 15.0  # limit is 10.0
    res = evaluate_supported_signals("BTC", factors, indicators, regime_state, last_close=62000.0, prev_bollinger_width=0.08)
    sig = res['bollinger_squeeze_breakout']
    assert sig['triggered'] is True
    assert sig['invalidated'] is True
    assert sig['active'] is False  # should be inactive because of invalidation!

def test_safe_eval_fail_safe():
    """Verify that malformed expressions evaluate to False safely and don't crash."""
    context = {"rsi_14": 50.0}
    # malformed expression (e.g. syntax error or security threat characters)
    assert safe_eval_expression("rsi_14 @ 50", context) is False
    assert safe_eval_expression("rsi_14 + unknown_var", context) is False
    assert safe_eval_expression("__import__('os').system('ls')", context) is False

def test_signal_only_execution_candidate_block():
    """Verify that signal_only signals do not become execution candidates in realtime engine."""
    engine = ResearchEngine(symbols=["BTC"])
    state = engine._get_state("BTC")
    
    # Set dummy state
    state.factors = {"live_ret_from_last_close": 0.0, "volatility_ratio_5_20": 0.5}
    state.indicators = {"BollingerWidth": 0.12}
    state.regime_state = {"regime": "range_chop", "tradable": True}
    
    # trigger volatility_squeeze_setup (which is signal_only)
    state.signals = {
        "volatility_squeeze_setup": {
            "triggered": True,
            "confirmed": True,
            "invalidated": False,
            "active": True,
            "direction": "signal_only",
            "template_family": "volatility_event"
        }
    }
    
    # Run strategy computation
    # Add dummy closes to pass bar count check (requires >= 35 closes)
    state._closes = [100.0] * 50
    engine._compute_strategies(state)
    
    strat = state.strategies['volatility_squeeze_setup']
    assert strat['status'] == 'standby'  # Must be standby even if signal is active!
    assert strat['logic_ready'] is False  # Must not be logic ready!
