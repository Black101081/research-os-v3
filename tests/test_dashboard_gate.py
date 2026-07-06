import pytest
import time
from unittest.mock import MagicMock, patch
from collections import deque
from dashboard_presenter import (
    _gate_summary, get_gate_payload, get_rejections_payload,
    get_overview_payload, get_signals_payload, get_dashboard_payload,
)
import globals as _globals


# ── Fixtures ──────────────────────────────────────────────────────────

def make_mock_gate(
    active_count=2,
    heat=3.5,
    equity=10_000.0,
    regime="trending",
    btc_structure="bullish",
    session="london",
    rejection_log=None,
    active_signals=None,
    cooldown=None,
):
    gate = MagicMock()
    gate.gate_summary = {
        "active_signal_count":   active_count,
        "portfolio_heat_pct":    heat,
        "account_equity_usd":    equity,
        "market_regime":         regime,
        "btc_structure":         btc_structure,
        "session_name":          session,
        "max_concurrent":        4,
        "max_heat_pct":          6.0,
        "gate_enabled":          True,
        "cooldown_count":        len(cooldown or {}),
    }
    gate._cfg = MagicMock()
    gate._cfg.enabled = True
    gate._cfg.portfolio.cooldown_seconds = 300
    gate._cfg.portfolio.max_concurrent_signals = 4
    gate._cfg.portfolio.max_signals_per_cluster = 2
    gate._cfg.portfolio.max_portfolio_heat_pct = 6.0
    gate._cfg.regime.anchor_symbol = "BTC"
    gate._cfg.session.enabled = True
    gate._cfg.regime.enabled = True
    gate._cfg.portfolio.enabled = True
    gate._cfg.statistical.enabled = True
    gate._cfg.statistical.min_confidence = 0.50
    gate._cfg.statistical.min_rr_ratio = 1.5
    gate._cfg.statistical.min_ev_r = 0.05
    gate._cfg.statistical.family_win_rates = {"continuation": 0.52}
    gate._cfg.regime.family_regime_map = {"continuation": "trend_only"}
    gate._cfg.portfolio.correlation_clusters = {"BTC": "crypto_majors"}
    gate._cfg.sizing.enabled = True
    gate._cfg.sizing.kelly_fraction = 0.5
    gate._cfg.sizing.min_position_pct = 0.5
    gate._cfg.sizing.max_position_pct = 5.0
    gate._cfg.sizing.account_equity = equity
    gate.rejection_log = deque(rejection_log or [], maxlen=100)
    gate._active_signals = active_signals or {}
    gate._cooldown = cooldown or {}
    gate._portfolio_heat = heat
    return gate


def make_mock_globals():
    mock_engine = MagicMock()
    mock_engine.snapshot.return_value = {}

    mock_broker = MagicMock()
    mock_broker.get_summary.return_value = {
        "positions": [], "trade_history": [],
        "balance": 10000.0, "equity": 10000.0,
        "active_positions_count": 0,
    }
    mock_broker.get_qualified_signals.return_value = []

    mock_telemetry = MagicMock()
    mock_telemetry.get_metrics.return_value = {
        "avg_latency_ms": 5.0,
        "error_rate_pct": 0.1,
        "uptime_seconds": 3600,
    }

    return mock_engine, mock_broker, mock_telemetry


# ── Tests: _gate_summary ──────────────────────────────────────────────

def test_gate_summary_no_gate(monkeypatch):
    monkeypatch.setattr(_globals, "quality_gate", None)
    summary = _gate_summary()
    assert summary["gate_enabled"] is False
    assert summary["active_signal_count"] == 0
    assert summary["portfolio_heat_pct"] == 0.0
    assert summary["market_regime"] == "unknown"


def test_gate_summary_with_gate(monkeypatch):
    gate = make_mock_gate(active_count=3, heat=4.2, regime="choppy")
    monkeypatch.setattr(_globals, "quality_gate", gate)
    summary = _gate_summary()
    assert summary["gate_enabled"] is True
    assert summary["active_signal_count"] == 3
    assert summary["portfolio_heat_pct"] == 4.2
    assert summary["market_regime"] == "choppy"


# ── Tests: get_gate_payload ───────────────────────────────────────────

def test_get_gate_payload_no_gate(monkeypatch):
    monkeypatch.setattr(_globals, "quality_gate", None)
    mock_engine, mock_broker, mock_telemetry = make_mock_globals()
    monkeypatch.setattr(_globals, "engine", mock_engine)
    monkeypatch.setattr(_globals, "broker", mock_broker)

    payload = get_gate_payload()

    assert "gate_summary" in payload
    assert payload["gate_summary"]["gate_enabled"] is False
    assert payload["active_slots"] == []
    assert payload["cooldown_map"] == []
    assert payload["qualified_feed"] == []
    assert payload["gate_config"] == {}


def test_get_gate_payload_with_gate(monkeypatch):
    active_signals = {
        "sig_BTC_1": ("BTC", "crypto_majors"),
        "sig_ETH_1": ("ETH", "crypto_majors"),
    }
    cooldown = {
        "BTC_continuation_long": time.time() - 60,   # 60s ago
    }
    gate = make_mock_gate(
        active_count=2,
        heat=2.5,
        active_signals=active_signals,
        cooldown=cooldown,
    )
    monkeypatch.setattr(_globals, "quality_gate", gate)
    mock_engine, mock_broker, mock_telemetry = make_mock_globals()
    monkeypatch.setattr(_globals, "engine", mock_engine)
    monkeypatch.setattr(_globals, "broker", mock_broker)

    payload = get_gate_payload()

    assert payload["gate_summary"]["active_signal_count"] == 2
    assert len(payload["active_slots"]) == 2
    assert len(payload["cooldown_map"]) == 1
    assert payload["cooldown_map"][0]["cooldown_key"] == "BTC_continuation_long"
    assert 0 < payload["cooldown_map"][0]["remaining_seconds"] <= 300
    assert "gate_config" in payload
    assert payload["gate_config"]["min_confidence"] == 0.50


def test_get_gate_payload_qualified_feed(monkeypatch):
    gate = make_mock_gate()
    monkeypatch.setattr(_globals, "quality_gate", gate)
    mock_engine, mock_broker, mock_telemetry = make_mock_globals()

    qs_dict = {
        "signal_id": "BTC_continuation_15m_test",
        "symbol": "BTC", "family": "continuation",
        "direction": "long", "entry_price": 50000.0,
        "position_size_pct": 2.5, "position_size_usd": 250.0,
        "expected_value_r": 0.65, "market_regime": "trending",
    }
    mock_broker.get_qualified_signals.return_value = [qs_dict]
    monkeypatch.setattr(_globals, "engine", mock_engine)
    monkeypatch.setattr(_globals, "broker", mock_broker)

    payload = get_gate_payload()
    assert len(payload["qualified_feed"]) == 1
    assert payload["qualified_feed"][0]["symbol"] == "BTC"
    assert payload["qualified_feed"][0]["position_size_pct"] == 2.5


# ── Tests: get_rejections_payload ────────────────────────────────────

def test_get_rejections_no_gate(monkeypatch):
    monkeypatch.setattr(_globals, "quality_gate", None)
    payload = get_rejections_payload()
    assert payload["rejections"] == []
    assert payload["total_count"] == 0
    assert payload["gate_enabled"] is False


def test_get_rejections_with_data(monkeypatch):
    from quality_gate_models import GateRejection, LayerResult, GATE_BLOCK

    r1 = GateRejection(
        signal_id="BTC_cont_1", symbol="BTC",
        family="continuation", direction="long",
        blocked_by_layer="regime",
        block_reason="regime_filter",
        layer_results=[
            LayerResult("session", "pass", ""),
            LayerResult("regime", GATE_BLOCK, "regime_filter",
                        {"current_regime": "choppy"}),
        ],
    )
    r2 = GateRejection(
        signal_id="ETH_cont_1", symbol="ETH",
        family="continuation", direction="long",
        blocked_by_layer="portfolio",
        block_reason="cooldown_filter",
        layer_results=[
            LayerResult("session", "pass", ""),
            LayerResult("regime",    "pass", ""),
            LayerResult("portfolio", GATE_BLOCK, "cooldown_filter", {}),
        ],
    )

    gate = make_mock_gate(rejection_log=[r1, r2])
    monkeypatch.setattr(_globals, "quality_gate", gate)

    payload = get_rejections_payload(limit=50)

    assert payload["total_count"] == 2
    assert len(payload["rejections"]) == 2
    # Mới nhất trước → r2 là index 0
    assert payload["rejections"][0]["blocked_by_layer"] == "portfolio"
    assert payload["rejections"][1]["blocked_by_layer"] == "regime"
    # Stats
    assert payload["stats"]["by_layer"]["regime"] == 1
    assert payload["stats"]["by_layer"]["portfolio"] == 1
    assert payload["stats"]["by_symbol"]["BTC"] == 1
    assert payload["stats"]["by_symbol"]["ETH"] == 1


def test_get_rejections_limit(monkeypatch):
    from quality_gate_models import GateRejection
    rejections = [
        GateRejection(
            signal_id=f"sig_{i}", symbol="BTC",
            family="continuation", direction="long",
            blocked_by_layer="regime", block_reason="regime_filter",
        )
        for i in range(20)
    ]
    gate = make_mock_gate(rejection_log=rejections)
    monkeypatch.setattr(_globals, "quality_gate", gate)

    payload = get_rejections_payload(limit=5)
    assert len(payload["rejections"]) == 5


# ── Tests: get_overview_payload includes gate ─────────────────────────

def test_overview_includes_quality_gate_section(monkeypatch):
    gate = make_mock_gate(heat=3.0, regime="trending")
    monkeypatch.setattr(_globals, "quality_gate", gate)
    mock_engine, mock_broker, mock_telemetry = make_mock_globals()
    monkeypatch.setattr(_globals, "engine",    mock_engine)
    monkeypatch.setattr(_globals, "broker",    mock_broker)
    monkeypatch.setattr(_globals, "telemetry", mock_telemetry)
    monkeypatch.setattr(_globals, "trading_mode",       "paper")
    monkeypatch.setattr(_globals, "kill_switch_active", False)
    monkeypatch.setattr(_globals, "CONFIG", {
        "symbols": ["BTC"], "candle_interval": "15m",
    })

    payload = get_overview_payload()

    assert "quality_gate" in payload["overview"]
    qg = payload["overview"]["quality_gate"]
    assert qg["portfolio_heat_pct"] == 3.0
    assert qg["market_regime"] == "trending"
    assert "heat_utilization_pct" in qg
    assert qg["heat_utilization_pct"] == 50.0   # 3.0 / 6.0 * 100


def test_overview_positions_include_gate_fields(monkeypatch):
    gate = make_mock_gate()
    monkeypatch.setattr(_globals, "quality_gate", gate)
    mock_engine, mock_broker, mock_telemetry = make_mock_globals()
    mock_broker.get_summary.return_value = {
        "positions": [{
            "symbol": "BTC", "direction": "long",
            "quantity": 0.005, "entry_price": 50000.0,
            "current_price": 51000.0, "unrealized_pnl": 5.0,
            "stop_loss": 49000.0, "take_profit": 52500.0,
            "entry_time": "2026-07-06T00:00:00Z",
            "position_size_pct": 2.5, "position_size_usd": 250.0,
            "risk_amount_usd": 10.0, "expected_value_r": 0.65,
        }],
        "trade_history": [],
        "balance": 10000.0, "equity": 10000.0,
        "active_positions_count": 1,
    }
    monkeypatch.setattr(_globals, "engine",    mock_engine)
    monkeypatch.setattr(_globals, "broker",    mock_broker)
    monkeypatch.setattr(_globals, "telemetry", mock_telemetry)
    monkeypatch.setattr(_globals, "trading_mode",       "paper")
    monkeypatch.setattr(_globals, "kill_switch_active", False)
    monkeypatch.setattr(_globals, "CONFIG", {
        "symbols": ["BTC"], "candle_interval": "15m",
    })

    payload = get_overview_payload()
    positions = payload["paper_positions"]["positions"]
    assert len(positions) == 1
    assert positions[0]["position_size_pct"] == 2.5
    assert positions[0]["position_size_usd"] == 250.0
    assert positions[0]["risk_amount_usd"] == 10.0


def test_get_dashboard_payload(monkeypatch):
    gate = make_mock_gate()
    monkeypatch.setattr(_globals, "quality_gate", gate)
    mock_engine, mock_broker, mock_telemetry = make_mock_globals()
    monkeypatch.setattr(_globals, "engine",    mock_engine)
    monkeypatch.setattr(_globals, "broker",    mock_broker)
    monkeypatch.setattr(_globals, "telemetry", mock_telemetry)
    monkeypatch.setattr(_globals, "trading_mode",       "paper")
    monkeypatch.setattr(_globals, "kill_switch_active", False)
    monkeypatch.setattr(_globals, "CONFIG", {
        "symbols": ["BTC"], "candle_interval": "15m",
    })

    payload = get_dashboard_payload()
    assert "gate" in payload
    assert payload["gate"]["gate_enabled"] is True
