from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import time
from hyperliquid_ws_client import HyperliquidWSClient
from strategy_spec_builder import build_strategy_spec_v1
from playbook_bridge import build_playbook_packet
from bootstrap_ohlcv import warmup_engine
from paper_replay import run_paper_replay_demo
from validator_runner import run_validator
from backtest_bridge import build_bridge_demo
from baseline_backtest_runner import run_backtest_runner_demo

import database as db
db.init_db()
db.prune_old_records(keep_days=30)

from globals import CONFIG, engine, registry, telemetry, broker, BASE
engine._paper_broker = broker
from routers import presets, brief, playbook, live_control
from dashboard_presenter import (
    get_dashboard_payload, get_overview_payload,
    get_signals_payload, get_signal_detail,
    get_gate_payload, get_rejections_payload,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
if os.path.isdir("/data"):
    logger.info("[STORAGE] ✅ /data mounted — using persistent storage at /data/research.db")
else:
    logger.warning("[STORAGE] ⚠️ /data NOT mounted — falling back to ./research.db (data will be lost on restart)")

ws_client = None
ws_task = None
writer_task = None
registry_task = None


def build_subscriptions() -> List[Dict[str, Any]]:
    subs = []
    asset_config = CONFIG.get("asset_config", {})
    active_symbols = set(CONFIG.get("symbols", []))

    # Multi-TF subscription
    for symbol, cfg in asset_config.items():
        if symbol not in active_symbols:
            continue
        for interval in cfg.get("candle_intervals", ["1m"]):
            subs.append({"type": "candle", "coin": symbol, "interval": interval})
        subs.append({"type": "trades", "coin": symbol})
        subs.append({"type": "bbo",    "coin": symbol})
        if cfg.get("subscribe_l2book", False):
            subs.append({"type": "l2Book",         "coin": symbol})
        if cfg.get("subscribe_active_asset_ctx", False):
            subs.append({"type": "activeAssetCtx", "coin": symbol})

    return subs


def build_specs_and_packets(snapshot: Dict[str, Any]) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    specs, packets = [], []
    for symbol, state in snapshot.items():
        for signal_name, signal_payload in state.get('signals', {}).items():
            strategy = state.get('strategies', {}).get(signal_name, {})
            if signal_payload.get('active') and strategy.get('execution_ready'):
                spec = build_strategy_spec_v1(symbol, signal_name, signal_payload, state, CONFIG)
                packet = build_playbook_packet(spec)
                specs.append(spec)
                packets.append(packet)
    return specs, packets


async def writer_loop() -> None:
    while True:
        snapshot = engine.snapshot()
        
        specs, packets = build_specs_and_packets(snapshot)
        try:
            await asyncio.wait_for(registry.write_snapshot(snapshot), timeout=5.0)
            await asyncio.wait_for(registry.append_strategy_specs(specs), timeout=5.0)
            await asyncio.wait_for(registry.append_playbook_packets(packets), timeout=5.0)
            await asyncio.wait_for(registry.append_strategy_candidates(snapshot), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("[writer_loop] Registry write timed out — skipping cycle")
        except Exception as e:
            logger.error(f"Registry write failed: {e}")

        # ── Persist specs + packets to SQLite ──
        try:
            for spec in specs:
                db.save_strategy_spec(
                    symbol=spec.get("symbol", "unknown"),
                    strategy=spec.get("strategy_name", "unknown"),
                    spec=spec
                )
            for packet in packets:
                db.save_playbook_packet(
                    symbol=packet.get("symbol", "unknown"),
                    strategy=packet.get("strategy_name", "unknown"),
                    packet=packet
                )
        except Exception as e:
            logger.error(f"[DB] Failed to persist specs/packets: {e}")

        # ── Persist validation snapshots to SQLite (every cycle) ──
        try:
            for symbol, state in snapshot.items():
                vp = state.get("validation_packet")
                if vp:
                    db.save_validation_snapshot(symbol, vp)
        except Exception as e:
            logger.error(f"[DB] Failed to persist validation: {e}")

        await asyncio.sleep(CONFIG['runtime']['write_every_seconds'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ws_client, ws_task, writer_task, registry_task
    try:
        warmup_engine(
            engine,
            CONFIG['symbols'],
            CONFIG['candle_interval'],
            CONFIG['runtime']['warmup_bars'],
            asset_config=CONFIG.get('asset_config')
        )
    except Exception as e:
        logger.error(f"Warmup failed: {e}. Proceeding without warmup.")
    async def on_message_wrapper(msg):
        t_start = time.perf_counter()
        try:
            engine.process_message(msg)
            telemetry.record_success(time.perf_counter() - t_start)
        except Exception as e:
            telemetry.record_error()
            logger.error(f"WS process message failed: {e}")
    ws_client = HyperliquidWSClient(url=CONFIG['ws_url'], subscriptions=build_subscriptions(), on_message=on_message_wrapper)
    ws_task = asyncio.create_task(ws_client.run_forever())
    registry_task = asyncio.create_task(registry.run())
    writer_task = asyncio.create_task(writer_loop())
    logger.info('Research OS started')
    try:
        yield
    finally:
        if ws_client is not None:
            await ws_client.close()
        if ws_task is not None:
            ws_task.cancel()
        if writer_task is not None:
            writer_task.cancel()
        if registry_task is not None:
            registry_task.cancel()
            await registry.close()
        logger.info('Research OS stopped')


app = FastAPI(title='Research OS V3', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')

app.include_router(presets.router)
app.include_router(brief.router)
app.include_router(playbook.router)
app.include_router(live_control.router)


@app.get('/health')
@app.get('/api/health')
def health() -> Dict[str, Any]:
    snapshot = engine.snapshot()
    active_counts = {symbol: len([s for s in state.get('signals', {}).values() if s.get('active')]) for symbol, state in snapshot.items()}
    return {'status': 'ok', 'ok': True, 'symbols': list(snapshot.keys()), 'active_signal_counts': active_counts}


@app.get("/api/health/storage")
async def health_storage():
    import os, sqlite3
    mounted = os.path.isdir("/data")
    db_path = "/data/research.db" if mounted else "./research.db"
    db_exists = os.path.isfile(db_path)
    db_size_kb = round(os.path.getsize(db_path) / 1024, 1) if db_exists else 0
    
    trade_count = 0
    position_count = 0
    if db_exists:
        try:
            conn = sqlite3.connect(db_path)
            trade_count = conn.execute(
                "SELECT COUNT(*) FROM trade_history"
            ).fetchone()[0]
            position_count = conn.execute(
                "SELECT COUNT(*) FROM paper_positions"
            ).fetchone()[0]
            conn.close()
        except Exception:
            pass
    
    return {
        "storage_mounted": mounted,
        "db_path": db_path,
        "db_exists": db_exists,
        "db_size_kb": db_size_kb,
        "trade_count": trade_count,
        "open_positions": position_count,
        "status": "persistent" if mounted else "ephemeral"
    }


@app.get('/api/config')
def get_config() -> Dict[str, Any]:
    return CONFIG


@app.post('/api/config/update')
async def update_config(data: Dict[str, Any]) -> Dict[str, Any]:
    global ws_client, ws_task, CONFIG
    new_symbols = data.get('symbols')
    new_interval = data.get('candle_interval')
    
    if not new_symbols or not new_interval:
        return {'status': 'error', 'message': 'Missing symbols or candle_interval'}
        
    if isinstance(new_symbols, str):
        new_symbols = [s.strip().upper() for s in new_symbols.split(',') if s.strip()]
        
    try:
        # 1. Close current WS client
        if ws_client is not None:
            await ws_client.close()
        if ws_task is not None:
            ws_task.cancel()
            
        # 2. Update and save CONFIG
        CONFIG['symbols'] = new_symbols
        CONFIG['candle_interval'] = new_interval
        
        # Auto-configure missing symbols in asset_config
        asset_config = CONFIG.setdefault('asset_config', {})
        for s in new_symbols:
            if s not in asset_config:
                asset_config[s] = {
                    "candle_intervals": ["1m", "5m", "15m", "1h"],
                    "subscribe_l2book": True,
                    "subscribe_active_asset_ctx": True,
                    "role": "alt",
                    "min_spread_bps": 2.0,
                    "max_spread_bps": 15.0,
                    "notes": "Auto-configured on UI addition."
                }
                
        config_path = BASE / 'config.json'
        config_path.write_text(json.dumps(CONFIG, indent=2), encoding='utf-8')
        
        # 3. Hot-reinitialize ResearchEngine state keys
        from realtime_engine import SymbolState
        from collections import deque
        engine.states = {s: SymbolState(symbol=s, bars=deque(maxlen=CONFIG['runtime']['max_bars'])) for s in new_symbols}
        
        # 4. Perform Warmup Bootstrap
        try:
            warmup_engine(
                engine,
                new_symbols,
                new_interval,
                CONFIG['runtime']['warmup_bars'],
                asset_config=CONFIG.get('asset_config')
            )
        except Exception as e:
            logger.error(f"Warmup failed during reload: {e}")
            
        # 5. Create new Websocket Client and launch task
        async def on_message_wrapper(msg):
            t_start = time.perf_counter()
            try:
                engine.process_message(msg)
                telemetry.record_success(time.perf_counter() - t_start)
            except Exception as e:
                telemetry.record_error()
                logger.error(f"WS process message failed: {e}")
                
        ws_client = HyperliquidWSClient(url=CONFIG['ws_url'], subscriptions=build_subscriptions(), on_message=on_message_wrapper)
        ws_task = asyncio.create_task(ws_client.run_forever())
        
        # Clear caches on hot reload
        global _replay_cache, _validator_cache, _backtest_cache
        _replay_cache = None
        _validator_cache = None
        _backtest_cache = None

        logger.info(f"Pipeline hot-reloaded successfully: {new_symbols} - {new_interval}")
        return {'status': 'ok', 'message': f'Successfully updated config and hot-reloaded pipeline for {new_symbols} on {new_interval}!'}
    except Exception as e:
        logger.error(f"Failed to hot-reload config: {e}")
        return {'status': 'error', 'message': str(e)}


@app.get('/api/dashboard')
def get_dashboard() -> JSONResponse:
    return JSONResponse(get_dashboard_payload())


@app.get('/api/dashboard/overview')
def get_dashboard_overview() -> JSONResponse:
    return JSONResponse(get_overview_payload())


@app.get('/api/dashboard/signals')
def get_dashboard_signals() -> JSONResponse:
    return JSONResponse(get_signals_payload())


@app.get('/api/signal/{symbol}/{signal_id}')
def get_signal_route_detail(symbol: str, signal_id: str) -> JSONResponse:
    detail = get_signal_detail(symbol, signal_id)
    if detail is None:
        return JSONResponse({'status': 'error', 'message': f'Signal {signal_id} for symbol {symbol} not found'}, status_code=404)
    return JSONResponse(detail)


@app.get("/api/gate")
def get_gate_status() -> JSONResponse:
    """
    Quality Gate state: portfolio heat, cooldowns, active slots,
    qualified signal feed, và gate config.
    """
    return JSONResponse(get_gate_payload())


@app.get("/api/gate/rejections")
def get_gate_rejections(limit: int = 50) -> JSONResponse:
    """
    Danh sách GateRejection gần nhất để debug.
    ?limit=N để giới hạn số lượng (default 50, max 100).
    """
    actual_limit = min(limit, 100)
    return JSONResponse(get_rejections_payload(limit=actual_limit))


@app.get('/snapshot')
@app.get('/api/snapshot')
def snapshot() -> JSONResponse:
    return JSONResponse(engine.snapshot())


@app.get('/api/validation')
def get_validation() -> Dict[str, Any]:
    snap = engine.snapshot()
    return {symbol: state.get('validation_packet', {}) for symbol, state in snap.items()}


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open('r', encoding='utf-8') as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except Exception:
        return []


@app.get('/api/specs')
def get_specs() -> Dict[str, Any]:
    specs = read_jsonl(registry.specs_file)
    packets = read_jsonl(registry.playbook_file)
    return {
        'strategy_specs': specs,
        'playbook_packets': packets
    }


_replay_cache = None
_validator_cache = None
_backtest_cache = None


@app.get('/replay-demo')
@app.get('/api/replay-demo')
def replay_demo() -> JSONResponse:
    global _replay_cache
    if _replay_cache is None:
        _replay_cache = run_paper_replay_demo(CONFIG)
    return JSONResponse(_replay_cache)


@app.get('/validator-report')
@app.get('/api/research-validator')
def validator_report() -> JSONResponse:
    global _validator_cache
    if _validator_cache is None:
        saved_file = BASE / 'runtime' / 'research_validator_report.json'
        if saved_file.exists():
            try:
                _validator_cache = json.loads(saved_file.read_text(encoding='utf-8'))
                logger.info("[CACHE] Loaded research_validator_report from file")
            except Exception as e:
                logger.error(f"[CACHE] Failed to load research_validator_report from file: {e}")
        if _validator_cache is None:
            _validator_cache = run_validator()
    return JSONResponse(_validator_cache)


@app.get('/backtest-bridge-demo')
@app.get('/api/backtest-bridge-demo')
def backtest_bridge_demo() -> JSONResponse:
    return JSONResponse(build_bridge_demo())


@app.get('/backtest-runner-demo')
@app.get('/api/backtest-runner-demo')
def backtest_runner_demo() -> JSONResponse:
    global _backtest_cache
    if _backtest_cache is None:
        saved_file = BASE / 'runtime' / 'backtest_runner_demo.json'
        if saved_file.exists():
            try:
                _backtest_cache = json.loads(saved_file.read_text(encoding='utf-8'))
                logger.info("[CACHE] Loaded backtest_runner_demo from file")
            except Exception as e:
                logger.error(f"[CACHE] Failed to load backtest_runner_demo from file: {e}")
        if _backtest_cache is None:
            _backtest_cache = run_backtest_runner_demo()
    return JSONResponse(_backtest_cache)


@app.get('/api/positions')
def get_positions() -> Dict[str, Any]:
    return broker.get_summary()






@app.get('/api/ranking')
def get_ranking() -> Dict[str, Any]:
    snap = engine.snapshot()
    backtest_data = {}
    
    backtest_file = BASE / 'runtime' / 'backtest_runner_demo.json'
    if backtest_file.exists():
        try:
            bt_results = json.loads(backtest_file.read_text(encoding='utf-8'))
            for res in bt_results.get('results', []):
                backtest_data[res.get('strategy_family')] = res.get('runner_metrics', {})
        except Exception:
            pass

    ranked = []
    for symbol, state in snap.items():
        validation = state.get('validation_packet', {})
        decay_detected = validation.get('decay_detected', False)
        code_valid = validation.get('code_valid', True)
        
        for name, strat in state.get('strategies', {}).items():
            metrics = backtest_data.get(name, {})
            net_pnl = metrics.get('net_pnl', 0.0)
            win_rate = metrics.get('win_rate', 0.5)
            
            pnl_norm = min(1.0, max(0.0, net_pnl / 100.0)) if net_pnl > 0 else 0.0
            perf_score = 0.5 * pnl_norm + 0.5 * win_rate
            
            r_state = state.get('regime_state', {})
            confidence = r_state.get('confidence', 0.5)
            tradable = r_state.get('tradable', False)
            robust_score = confidence * 0.8 + 0.2 if tradable else 0.0
            
            decay_score = 0.0 if decay_detected else 1.0
            complexity_score = 1.0 if code_valid else 0.0
            
            comp_score = (
                0.35 * perf_score +
                0.25 * robust_score +
                0.20 * decay_score +
                0.20 * complexity_score
            )
            
            if comp_score >= 0.75 and not decay_detected and code_valid:
                decision = "AUTO_PROMOTE"
            elif comp_score < 0.50 or decay_detected or not code_valid:
                decision = "AUTO_REVISE"
            else:
                decision = "STANDBY"
                
            ranked.append({
                'symbol': symbol,
                'strategy_name': name,
                'composite_score': round(comp_score, 3),
                'perf_score': round(perf_score, 3),
                'robust_score': round(robust_score, 3),
                'decay_score': round(decay_score, 3),
                'complexity_score': round(complexity_score, 3),
                'decay_detected': decay_detected,
                'code_valid': code_valid,
                'decision': decision,
                'net_pnl': net_pnl,
                'win_rate': win_rate,
                'status': strat.get('status')
            })
            
    ranked.sort(key=lambda x: x['composite_score'], reverse=True)
    for i, item in enumerate(ranked):
        item['rank'] = i + 1
        
    # Persist ranking snapshot to SQLite
    try:
        db.save_ranking_snapshot(ranked)
    except Exception as e:
        logger.error(f"[DB] Failed to persist ranking: {e}")

    return {
        'ranked_strategies': ranked,
        'rules': {
            'promote_threshold': 0.75,
            'revise_threshold': 0.50,
            'metrics_weights': {
                'performance': 0.35,
                'robustness': 0.25,
                'decay': 0.20,
                'complexity': 0.20
            }
        }
    }


@app.get('/api/ranking/history')
def get_ranking_history(symbol: str = None, limit: int = 200) -> Dict[str, Any]:
    rows = db.load_ranking_history(symbol=symbol, limit=limit)
    return {"ranking_history": rows, "count": len(rows)}


@app.get('/api/validation/history')
def get_validation_history(symbol: str, limit: int = 100) -> Dict[str, Any]:
    rows = db.load_validation_history(symbol=symbol, limit=limit)
    return {"symbol": symbol, "validation_history": rows, "count": len(rows)}


@app.get('/api/specs/history')
def get_specs_history(limit: int = 100) -> Dict[str, Any]:
    specs   = db.load_latest_strategy_specs(limit=limit)
    packets = db.load_latest_playbook_packets(limit=limit)
    return {
        "strategy_specs": specs,
        "playbook_packets": packets,
        "counts": {"specs": len(specs), "packets": len(packets)}
    }


@app.get('/api/equity-curve')
def get_equity_curve(limit: int = 1440) -> Dict[str, Any]:
    points = db.load_equity_curve(limit=limit)
    return {
        "equity_curve": points,
        "count": len(points),
        "latest": points[-1] if points else None
    }


@app.get('/api/order-log')
def get_order_log(limit: int = 200) -> Dict[str, Any]:
    logs = db.load_order_log(limit=limit)
    accepted = [l for l in logs if l["accepted"]]
    rejected = [l for l in logs if not l["accepted"]]
    return {
        "order_log": logs,
        "total": len(logs),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected)
    }


@app.get('/api/system-events')
def get_system_events(limit: int = 100) -> Dict[str, Any]:
    events = db.load_system_events(limit=limit)
    return {"system_events": events, "count": len(events)}


@app.get('/api/telemetry')
def get_telemetry() -> Dict[str, Any]:
    import globals
    snap = engine.snapshot()
    ready_count = 0
    for symbol, state in snap.items():
        for strategy in state.get('strategies', {}).values():
            if strategy.get('execution_ready'):
                ready_count += 1
    metrics = telemetry.get_metrics(active_candidates=ready_count)
    metrics['kill_switch_active'] = globals.kill_switch_active
    metrics['trading_mode'] = globals.trading_mode
    return metrics



@app.get('/')
def dashboard() -> FileResponse:
    return FileResponse(BASE / 'static' / 'index.html')


if __name__ == '__main__':
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=False)
