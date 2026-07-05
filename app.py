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

from hyperliquid_ws_client import HyperliquidWSClient
from realtime_engine import ResearchEngine
from registry_writer import RegistryWriter
from strategy_spec_builder import build_strategy_spec_v1
from playbook_bridge import build_playbook_packet
from bootstrap_ohlcv import warmup_engine
from paper_replay import run_paper_replay_demo
from validator_runner import run_validator
from backtest_bridge import build_bridge_demo
from baseline_backtest_runner import run_backtest_runner_demo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'config.example.json').read_text())

engine = ResearchEngine(symbols=CONFIG['symbols'], max_bars=CONFIG['runtime']['max_bars'], thresholds=CONFIG['thresholds'])
registry = RegistryWriter(BASE / 'runtime')
ws_client = None
ws_task = None
writer_task = None


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
        registry.write_snapshot(snapshot)
        specs, packets = build_specs_and_packets(snapshot)
        registry.append_strategy_specs(specs)
        registry.append_playbook_packets(packets)
        registry.append_strategy_candidates(snapshot)
        await asyncio.sleep(CONFIG['runtime']['write_every_seconds'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ws_client, ws_task, writer_task
    warmup_engine(engine, BASE / 'sample_data')
    ws_client = HyperliquidWSClient(url=CONFIG['ws_url'], subscriptions=build_subscriptions(), handler=engine.handle_message)
    ws_task = asyncio.create_task(ws_client.run_forever())
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
        logger.info('Research OS stopped')


app = FastAPI(title='Research OS V3', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')


@app.get('/health')
def health() -> Dict[str, Any]:
    snapshot = engine.snapshot()
    active_counts = {symbol: len([s for s in state.get('signals', {}).values() if s.get('active')]) for symbol, state in snapshot.items()}
    return {'ok': True, 'symbols': list(snapshot.keys()), 'active_signal_counts': active_counts}


@app.get('/snapshot')
def snapshot() -> JSONResponse:
    return JSONResponse(engine.snapshot())


@app.get('/replay-demo')
def replay_demo() -> JSONResponse:
    return JSONResponse(run_paper_replay_demo())


@app.get('/validator-report')
def validator_report() -> JSONResponse:
    return JSONResponse(run_validator())


@app.get('/backtest-bridge-demo')
def backtest_bridge_demo() -> JSONResponse:
    return JSONResponse(build_bridge_demo())


@app.get('/backtest-runner-demo')
def backtest_runner_demo() -> JSONResponse:
    return JSONResponse(run_backtest_runner_demo())


@app.get('/')
def dashboard() -> FileResponse:
    return FileResponse(BASE / 'static' / 'index.html')


if __name__ == '__main__':
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=False)
