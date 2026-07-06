from __future__ import annotations

import time
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from collections import deque

from quality_gate import (
    QualityGate, _calc_kelly_fraction, _calc_ev,
    _confidence_to_size_scale, _layer_session,
    _layer_regime, _layer_portfolio, _layer_statistical, _layer_sizing,
)
from quality_gate_models import (
    GATE_PASS, GATE_BLOCK,
    BLOCK_REASON_SESSION, BLOCK_REASON_REGIME,
    BLOCK_REASON_PORTFOLIO, BLOCK_REASON_STATISTICAL, BLOCK_REASON_COOLDOWN,
    QualityGateConfig, SessionConfig, RegimeConfig,
    PortfolioConfig, StatisticalConfig, SizingConfig,
    QualifiedSignal, GateRejection, LayerResult,
)
from signal_models import (
    DIRECTION_LONG, DIRECTION_SHORT,
    FAMILY_CONTINUATION, FAMILY_MEAN_REVERSION,
    FAMILY_BREAKOUT, FAMILY_FUNDING_REVERSION,
    SignalResult,
)
from multi_tf_state import MultiTFEngine, MultiTFSymbolState, TFState, TFBar


def make_signal(
    symbol="BTC", family=FAMILY_CONTINUATION,
    direction=DIRECTION_LONG, interval="15m",
    asset_role="anchor",
    confidence=0.72, rr_ratio=2.5,
    entry=50000.0, sl=49000.0, tp=52500.0,
) -> SignalResult:
    return SignalResult(
        signal_id=f"{symbol}_{family}_{interval}_test",
        symbol=symbol, family=family,
        interval=interval, asset_role=asset_role,
        fired=True, direction=direction,
        entry_price=entry, stop_loss=sl,
        take_profit=tp, confidence_score=confidence,
        confluence_votes=4, confluence_total=5,
        risk_reward_ratio=rr_ratio, atr_at_signal=200.0,
    )


def test_helper_calculations():
    # Kelly: win_rate=0.55, rr=2.0 -> (0.55 * 2.0 - 0.45) / 2.0 = 0.65 / 2.0 = 0.325
    assert abs(_calc_kelly_fraction(0.55, 2.0) - 0.325) < 1e-6
    # EV: win_rate=0.55, rr=2.0 -> 0.55 * 2.0 - 0.45 = 1.10 - 0.45 = 0.65
    assert abs(_calc_ev(0.55, 2.0) - 0.65) < 1e-6

    # Confidence scaling lookup
    size_map = {"0.50": 0.5, "0.70": 0.8, "0.90": 1.0}
    assert _confidence_to_size_scale(0.55, size_map) == 0.5
    assert _confidence_to_size_scale(0.72, size_map) == 0.8
    assert _confidence_to_size_scale(0.95, size_map) == 1.0
    assert _confidence_to_size_scale(0.45, size_map) == 0.0


@patch('quality_gate._utc_now')
def test_layer_session_pass(mock_now):
    # Mock London peak hours (10:00 UTC)
    mock_now.return_value = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)
    sig = make_signal()
    cfg = QualityGateConfig()
    res = _layer_session(sig, cfg)
    assert res.verdict == GATE_PASS
    assert res.metadata["session_name"] == "london"


@patch('quality_gate._utc_now')
def test_layer_session_dead_zone(mock_now):
    # Mock daily low-liquidity (23:00 UTC)
    mock_now.return_value = datetime(2026, 7, 6, 23, 0, tzinfo=timezone.utc)
    sig = make_signal()
    cfg = QualityGateConfig()
    res = _layer_session(sig, cfg)
    assert res.verdict == GATE_BLOCK
    assert res.reason == BLOCK_REASON_SESSION
    assert "dead_zone" in res.metadata


@patch('quality_gate._utc_now')
def test_layer_session_near_end(mock_now):
    # Tokyo session ends at 9:00 UTC. Mock 8:50 UTC (10 mins left)
    mock_now.return_value = datetime(2026, 7, 6, 8, 50, tzinfo=timezone.utc)
    sig = make_signal()
    cfg = QualityGateConfig()
    # Configure 15 mins block threshold
    cfg.session.block_near_session_end_minutes = 15
    res = _layer_session(sig, cfg)
    # Ends at 9:00, remaining < 15 -> should block or fall outside active session if London hasn't started yet.
    # Wait, at 8:50 London (7 to 16) is already active!
    # So London session is still active, which does not end soon. Thus Tokyo ending should not block it.
    # Let's test a time where ONLY Tokyo is active, e.g. 0:55 UTC (ends at 1:00 UTC or starts at 1:00?)
    # Tokyo active: 1 to 9. Let's mock 8:50 but disable London/NY sessions
    cfg.session.sessions = [(1, 9)]
    res = _layer_session(sig, cfg)
    assert res.verdict == GATE_BLOCK


def test_layer_regime_compat():
    # Setup mock multi-TF engine
    mtf = MagicMock(spec=MultiTFEngine)
    sym_state = MagicMock(spec=MultiTFSymbolState)
    tf_state = MagicMock(spec=TFState)
    tf_state.bars = [1, 2, 3]
    
    # 1. Trending regime
    tf_state.indicators = {"adx_14": 30.0, "ema_spread_8_21": 0.2, "rsi_14": 55.0}
    sym_state.get_tf.return_value = tf_state
    mtf.get.return_value = sym_state

    cfg = QualityGateConfig()
    
    # Continuation signal in trending regime -> should PASS
    sig_cont = make_signal(family=FAMILY_CONTINUATION)
    res = _layer_regime(sig_cont, mtf, cfg)
    assert res.verdict == GATE_PASS

    # Mean reversion in trending regime -> should BLOCK
    sig_mr = make_signal(family=FAMILY_MEAN_REVERSION)
    res = _layer_regime(sig_mr, mtf, cfg)
    assert res.verdict == GATE_BLOCK
    assert res.reason == BLOCK_REASON_REGIME


def test_layer_regime_btc_bear_structure_long_blocked():
    # Setup mock multi-TF engine with bear structure (ema_spread < -0.5)
    mtf = MagicMock(spec=MultiTFEngine)
    sym_state = MagicMock(spec=MultiTFSymbolState)
    tf_state = MagicMock(spec=TFState)
    tf_state.bars = [1, 2, 3]
    tf_state.indicators = {"adx_14": 30.0, "ema_spread_8_21": -0.8, "rsi_14": 40.0}
    sym_state.get_tf.return_value = tf_state
    mtf.get.return_value = sym_state

    cfg = QualityGateConfig()
    
    # Long continuation signal under BTC bear structure -> should BLOCK
    sig_long = make_signal(symbol="ETH", family=FAMILY_CONTINUATION, direction=DIRECTION_LONG)
    res = _layer_regime(sig_long, mtf, cfg)
    assert res.verdict == GATE_BLOCK
    assert "btc_bear_structure_blocks_longs" in res.metadata["reason"]


def test_layer_portfolio_concurrency_and_cooldown():
    cfg = QualityGateConfig()
    cfg.portfolio.max_concurrent_signals = 2
    cfg.portfolio.cooldown_seconds = 60

    active_signals = ["sig1", "sig2"]
    active_clusters = {"crypto_majors": 1}
    cooldown_registry = {}
    portfolio_heat = 2.0

    sig = make_signal()

    # Max concurrent reached -> should BLOCK
    res = _layer_portfolio(sig, active_signals, active_clusters, cooldown_registry, portfolio_heat, cfg)
    assert res.verdict == GATE_BLOCK
    assert res.reason == BLOCK_REASON_PORTFOLIO

    # Cooldown check
    active_signals = ["sig1"]
    cooldown_key = f"{sig.symbol}_{sig.family}_{sig.direction}"
    cooldown_registry[cooldown_key] = time.time() - 30  # fired 30s ago, cooldown is 60s
    res = _layer_portfolio(sig, active_signals, active_clusters, cooldown_registry, portfolio_heat, cfg)
    assert res.verdict == GATE_BLOCK
    assert res.reason == BLOCK_REASON_COOLDOWN


def test_layer_statistical_ev_gate():
    cfg = QualityGateConfig()
    cfg.statistical.min_ev_r = 0.05
    cfg.statistical.family_win_rates = {FAMILY_CONTINUATION: 0.52}

    # Low RR -> should BLOCK
    sig_low_rr = make_signal(confidence=0.60, rr_ratio=1.0)
    res, ev = _layer_statistical(sig_low_rr, cfg)
    assert res.verdict == GATE_BLOCK
    assert "rr_below_minimum" in res.metadata["reason"]

    # Valid signal -> should PASS
    sig_good = make_signal(confidence=0.80, rr_ratio=2.5)
    res, ev = _layer_statistical(sig_good, cfg)
    assert res.verdict == GATE_PASS
    assert ev > 0.10


def test_layer_sizing():
    cfg = QualityGateConfig()
    cfg.sizing.account_equity = 10000.0
    cfg.sizing.min_position_pct = 0.5
    cfg.sizing.max_position_pct = 5.0
    cfg.sizing.kelly_fraction = 0.5

    sig = make_signal(entry=50000.0, sl=49000.0)  # 2% SL distance
    res, size_pct, size_usd, risk_usd = _layer_sizing(sig, 0.20, cfg)
    assert res.verdict == GATE_PASS
    assert size_pct >= 0.5 and size_pct <= 5.0
    assert size_usd == size_pct / 100.0 * 10000.0
    assert risk_usd == size_usd * 0.02


@patch('quality_gate._utc_now')
def test_full_quality_gate_pipeline(mock_now):
    # Mock London peak hours
    mock_now.return_value = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)

    # Setup mock multi-TF engine
    mtf = MagicMock(spec=MultiTFEngine)
    sym_state = MagicMock(spec=MultiTFSymbolState)
    tf_state = MagicMock(spec=TFState)
    tf_state.bars = [1, 2, 3]
    tf_state.indicators = {"adx_14": 30.0, "ema_spread_8_21": 0.6, "rsi_14": 55.0}
    sym_state.get_tf.return_value = tf_state
    mtf.get.return_value = sym_state

    cfg = QualityGateConfig()
    gate = QualityGate(cfg, mtf)

    sig = make_signal(confidence=0.85, rr_ratio=2.2)
    res = gate.evaluate(sig)

    assert isinstance(res, QualifiedSignal)
    assert res.verdict == GATE_PASS
    assert res.position_size_pct > 0.0
    assert res.expected_value_r > 0.0
    
    # Test tracking registry
    assert gate.active_signal_count == 1
    assert gate.portfolio_heat > 0.0

    # Test closing signal
    gate.on_signal_closed(sig.signal_id)
    assert gate.active_signal_count == 0
