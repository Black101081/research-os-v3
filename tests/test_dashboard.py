from __future__ import annotations

import pytest
import json
from pathlib import Path
from dashboard_presenter import (
    get_dashboard_payload,
    get_overview_payload,
    get_signals_payload,
    get_signal_detail
)

def test_get_dashboard_payload():
    """Verify that get_dashboard_payload returns all expected fields with the correct structure."""
    payload = get_dashboard_payload()
    
    # 1. Verify top-level structure
    assert 'overview' in payload
    assert 'symbols' in payload
    assert 'signals' in payload
    assert 'paper_positions' in payload
    assert 'telemetry' in payload
    
    # 2. Verify overview
    over = payload['overview']
    assert 'mode' in over
    assert 'kill_switch_active' in over
    assert 'latency_ms' in over
    assert 'error_rate' in over
    assert 'uptime_seconds' in over
    assert 'active_signal_count' in over
    assert 'confirmed_signal_count' in over
    assert 'execution_ready_count' in over
    assert 'open_positions_count' in over
    assert 'symbols' in over
    assert 'candle_interval' in over
    
    # 3. Verify symbols
    assert isinstance(payload['symbols'], list)
    if len(payload['symbols']) > 0:
        sym = payload['symbols'][0]
        assert 'symbol' in sym
        assert 'last_trade' in sym
        assert 'mid' in sym
        assert 'updated_at' in sym
        assert 'regime' in sym
        assert 'regime_confidence' in sym
        assert 'tradable' in sym
        assert 'bars_loaded' in sym
        assert 'signal_summary' in sym
        assert 'top_signals' in sym
        
        sig_sum = sym['signal_summary']
        assert 'total' in sig_sum
        assert 'triggered' in sig_sum
        assert 'confirmed' in sig_sum
        assert 'active' in sig_sum
        assert 'invalidated' in sig_sum
        
    # 4. Verify signals
    assert isinstance(payload['signals'], list)
    if len(payload['signals']) > 0:
        sig = payload['signals'][0]
        assert 'symbol' in sig
        assert 'signal_id' in sig
        assert 'family' in sig
        assert 'direction' in sig
        assert 'triggered' in sig
        assert 'confirmed' in sig
        assert 'invalidated' in sig
        assert 'active' in sig
        assert 'confirmation_score' in sig
        assert 'invalidation_score' in sig
        assert 'quality_tier' in sig
        assert 'regime_fit' in sig
        assert 'thesis' in sig
        assert 'entry_logic_summary' in sig
        assert 'confirmation_summary' in sig
        assert 'invalidation_summary' in sig
        assert 'why' in sig
        
    # 5. Verify paper positions
    paper = payload['paper_positions']
    assert 'positions' in paper
    assert 'history' in paper
    assert 'balance' in paper
    assert 'equity' in paper


def test_get_overview_payload():
    payload = get_overview_payload()
    assert 'overview' in payload
    assert 'symbols' in payload
    assert 'paper_positions' in payload
    assert 'telemetry' in payload
    assert 'signals' not in payload


def test_get_signals_payload():
    payload = get_signals_payload()
    assert 'signals' in payload
    for s in payload['signals']:
        assert 'why' not in s


def test_get_signal_detail():
    sigs = get_signals_payload()['signals']
    if sigs:
        target = sigs[0]
        detail = get_signal_detail(target['symbol'], target['signal_id'])
        assert detail is not None
        assert detail['symbol'] == target['symbol']
        assert detail['signal_id'] == target['signal_id']
        assert 'why' in detail
    
    assert get_signal_detail('INVALID_SYM', 'invalid_sig') is None


def test_signal_detail_route():
    from fastapi.testclient import TestClient
    from app import app
    client = TestClient(app)
    
    sigs = get_signals_payload()['signals']
    if sigs:
        target = sigs[0]
        response = client.get(f"/api/signal/{target['symbol']}/{target['signal_id']}")
        assert response.status_code == 200
        data = response.json()
        assert data['symbol'] == target['symbol']
        assert 'why' in data
        
    response = client.get("/api/signal/INVALID_SYM/invalid_sig")
    assert response.status_code == 404
    assert response.json()['status'] == 'error'
