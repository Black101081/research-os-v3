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

from globals import CONFIG, engine, registry, telemetry, broker, BASE
from routers import presets, brief, playbook, live_control
from dashboard_presenter import get_dashboard_payload, get_overview_payload, get_signals_payload, get_signal_detail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ws_client = None
ws_task = None
writer_task = None
registry_task = None


def build_subscriptions() -> List[Dict[str, Any]]:
    subs: List[Dict[str, Any]] = []
    interval = CONFIG['candle_interval']
    for symbol in CONFIG['symbols']:
        if 'trades' in CONFIG['subscriptions']:
            subs.append({'type': 'trades', 'coin': symbol})
        if 'candle' in CONFIG['subscriptions']:
            subs.append({'type': 'candle', 'coin': symbol, 'interval': interval})
        if 'bbo' in CONFIG['subscriptions']:
            subs.append({'type': 'bbo', 'coin': symbol})
    if 'allMids' in CONFIG['subscriptions']:
        subs.append({'type': 'allMids'})
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
        
        # Process live paper broker ticks & entries
        for symbol, state in snapshot.items():
            current_price = state.get('last_trade') or state.get('mid')
            current_time = state.get('updated_at')
            if current_price:
                broker.process_tick(symbol, current_price, current_time)
                
            for strategy_name, strategy_state in state.get('strategies', {}).items():
                if strategy_state.get('execution_ready'):
                    risk = state.get('risk_packets', {}).get(strategy_name, {})
                    qty = risk.get('target_quantity', 0.0)
                    side = strategy_state.get('entry_side', 'long')
                    stop_policy = risk.get('stop_policy', {})
                    sl = stop_policy.get('initial_stop_price')
                    # Lấy từ risk packet trước
                    tp = risk.get('take_profit_price')
                    if tp is None:
                        bb_width = state.get('indicators', {}).get('BollingerWidth', 0.03)
                        tp_pct = max(0.01, bb_width)  # ít nhất 1%, scale theo vol
                        tp = current_price * (1 + tp_pct) if side == 'long' else current_price * (1 - tp_pct)
                    
                    broker.execute_order(
                        symbol=symbol,
                        direction=side,
                        quantity=qty,
                        price=current_price,
                        stop_loss=sl,
                        take_profit=tp,
                        time_str=current_time,
                        signal_source=strategy_name
                    )

        specs, packets = build_specs_and_packets(snapshot)
        try:
            await registry.write_snapshot(snapshot)
            await registry.append_strategy_specs(specs)
            await registry.append_playbook_packets(packets)
            await registry.append_strategy_candidates(snapshot)
        except Exception as e:
            logger.error(f"Registry write failed: {e}")
        await asyncio.sleep(CONFIG['runtime']['write_every_seconds'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ws_client, ws_task, writer_task, registry_task
    try:
        warmup_engine(engine, CONFIG['symbols'], CONFIG['candle_interval'], CONFIG['runtime']['warmup_bars'])
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
        config_path = BASE / 'config.json'
        config_path.write_text(json.dumps(CONFIG, indent=2), encoding='utf-8')
        
        # 3. Hot-reinitialize ResearchEngine state keys
        from realtime_engine import SymbolState
        from collections import deque
        engine.states = {s: SymbolState(symbol=s, bars=deque(maxlen=CONFIG['runtime']['max_bars'])) for s in new_symbols}
        
        # 4. Perform Warmup Bootstrap
        try:
            warmup_engine(engine, new_symbols, new_interval, CONFIG['runtime']['warmup_bars'])
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


@app.get('/replay-demo')
@app.get('/api/replay-demo')
def replay_demo() -> JSONResponse:
    return JSONResponse(run_paper_replay_demo(CONFIG))


@app.get('/validator-report')
@app.get('/api/research-validator')
def validator_report() -> JSONResponse:
    return JSONResponse(run_validator())


@app.get('/backtest-bridge-demo')
@app.get('/api/backtest-bridge-demo')
def backtest_bridge_demo() -> JSONResponse:
    return JSONResponse(build_bridge_demo())


@app.get('/backtest-runner-demo')
@app.get('/api/backtest-runner-demo')
def backtest_runner_demo() -> JSONResponse:
    return JSONResponse(run_backtest_runner_demo())


@app.get('/api/positions')
def get_positions() -> Dict[str, Any]:
    return broker.get_summary()






@app.get('/api/ranking')
def get_ranking() -> Dict[str, Any]:
    snap = engine.snapshot()
    backtest_data = {}
    
    backtest_file = Path('data/backtest_runner_demo.json')
    if backtest_file.exists():
        try:
            bt_results = json.loads(backtest_file.read_text())
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
