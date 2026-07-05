from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Body, Request, HTTPException
import globals

router = APIRouter(prefix="/api")
processed_tokens = set()

@router.post('/kill-switch')
def post_kill_switch(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    # 1. Double confirm check
    confirm = payload.get('confirm', '')
    if confirm != 'CONFIRM':
        raise HTTPException(
            status_code=400,
            detail="Emergency Stop requires explicit confirmation payload {'confirm': 'CONFIRM'}."
        )
        
    # 2. Idempotency token check
    token = payload.get('idempotency_token') or request.headers.get('x-idempotency-token')
    if token:
        if token in processed_tokens:
            return {
                'status': 'success',
                'kill_switch_active': globals.kill_switch_active,
                'message': 'Duplicate request processed via idempotency token.'
            }
        processed_tokens.add(token)
        
    # 3. Activate Kill Switch & Close open positions
    globals.kill_switch_active = True
    globals.broker.positions.clear()
    
    # 4. Log event with timestamp + user agent
    user_agent = request.headers.get('user-agent', 'unknown')
    log_dir = Path('data/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'kill_switch.log'
    log_message = f"[{datetime.now().isoformat()}] KILL SWITCH TRIGGERED | Token: {token} | UA: {user_agent}\n"
    
    with log_file.open('a', encoding='utf-8') as f:
        f.write(log_message)
        
    return {
        'status': 'success',
        'kill_switch_active': globals.kill_switch_active,
        'message': 'EMERGENCY KILL SWITCH ACTIVATED. Open positions closed.'
    }


@router.post('/toggle-trading-mode')
def post_toggle_trading_mode() -> Dict[str, Any]:
    globals.trading_mode = 'live_testnet' if globals.trading_mode == 'paper' else 'paper'
    return {
        'status': 'success',
        'trading_mode': globals.trading_mode
    }
