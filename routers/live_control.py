from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Body, Request, HTTPException
import globals

router = APIRouter(prefix="/api")

# Load processed idempotency tokens from file if it exists, keeping only last 1000 to limit size
token_file = Path('data/logs/processed_tokens.txt')
processed_tokens = set()
token_list = []
if token_file.exists():
    try:
        token_list = token_file.read_text(encoding='utf-8').splitlines()
        if len(token_list) > 1000:
            token_list = token_list[-1000:]
            token_file.write_text('\n'.join(token_list) + '\n', encoding='utf-8')
        processed_tokens = set(token_list)
    except Exception:
        pass

def save_token(token: str):
    global token_list
    if token in processed_tokens:
        return
    processed_tokens.add(token)
    token_list.append(token)
    try:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        if len(token_list) > 1000:
            token_list = token_list[-1000:]
            token_file.write_text('\n'.join(token_list) + '\n', encoding='utf-8')
        else:
            with token_file.open('a', encoding='utf-8') as f:
                f.write(token + '\n')
    except Exception:
        pass


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
        save_token(token)
        
    # 3. Activate Kill Switch & Close open positions
    globals.kill_switch_active = True
    globals.broker.clear_all_positions()
    
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


@router.post('/kill-switch/reset')
def post_kill_switch_reset(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    confirm = payload.get('confirm', '')
    if confirm != 'RESET':
        raise HTTPException(
            status_code=400,
            detail="Resetting Emergency Stop requires explicit confirmation payload {'confirm': 'RESET'}."
        )
    globals.kill_switch_active = False
    
    user_agent = request.headers.get('user-agent', 'unknown')
    log_dir = Path('data/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'kill_switch.log'
    log_message = f"[{datetime.now().isoformat()}] KILL SWITCH RESET | UA: {user_agent}\n"
    
    with log_file.open('a', encoding='utf-8') as f:
        f.write(log_message)
        
    return {
        'status': 'success',
        'kill_switch_active': globals.kill_switch_active,
        'message': 'Emergency Stop deactivated. System restored to active state.'
    }


@router.post('/toggle-trading-mode')
def post_toggle_trading_mode(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    confirm = payload.get('confirm', '')
    if confirm != 'TOGGLE':
        raise HTTPException(
            status_code=400,
            detail="Toggling trading mode requires explicit confirmation payload {'confirm': 'TOGGLE'}."
        )
    globals.trading_mode = 'live_testnet' if globals.trading_mode == 'paper' else 'paper'
    
    user_agent = request.headers.get('user-agent', 'unknown')
    log_dir = Path('data/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'kill_switch.log'
    log_message = f"[{datetime.now().isoformat()}] TRADING MODE TOGGLED to {globals.trading_mode} | UA: {user_agent}\n"
    
    with log_file.open('a', encoding='utf-8') as f:
        f.write(log_message)
        
    return {
        'status': 'success',
        'trading_mode': globals.trading_mode
    }
