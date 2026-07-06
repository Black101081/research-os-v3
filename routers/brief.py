from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Body
from globals import engine, registry, BASE
import database as db

router = APIRouter(prefix="/api")

@router.get('/research-brief/{symbol}/{strategy_name}')
def get_research_brief(symbol: str, strategy_name: str) -> Dict[str, Any]:
    snap = engine.snapshot()
    state = snap.get(symbol, {})
    if not state:
        return {'error': f'Symbol {symbol} not found'}
        
    validation = state.get('validation_packet') or {}
    decay_detected = validation.get('decay_detected', False)
    code_valid = validation.get('code_valid', True)
    
    r_state = state.get('regime_state') or {}
    regime = r_state.get('regime', 'unknown')
    confidence = r_state.get('confidence')
    
    net_pnl = 0.0
    win_rate = 0.5
    backtest_file = BASE / 'runtime' / 'backtest_runner_demo.json'
    if backtest_file.exists():
        try:
            bt_results = json.loads(backtest_file.read_text(encoding='utf-8'))
            for res in bt_results.get('results', []):
                if res.get('strategy_family') == strategy_name:
                    metrics = res.get('runner_metrics') or {}
                    net_pnl = metrics.get('net_pnl', 0.0)
                    win_rate = metrics.get('win_rate', 0.5)
        except Exception:
            pass

    factors = state.get('factors') or {}
    zscore = factors.get('zscore_close_20', 0.0)
    volatility = factors.get('volatility_20', 0.0)
    rel_volume = factors.get('rel_volume_20', 0.0)
    
    # Safe type conversions to avoid formatting errors on NoneType values
    try:
        net_pnl = float(net_pnl if net_pnl is not None else 0.0)
        win_rate = float(win_rate if win_rate is not None else 0.5) * 100
        confidence = float(confidence if confidence is not None else 0.0)
        zscore = float(zscore if zscore is not None else 0.0)
        volatility = float(volatility if volatility is not None else 0.0)
        rel_volume = float(rel_volume if rel_volume is not None else 0.0)
    except Exception:
        net_pnl = 0.0
        win_rate = 50.0
        confidence = 0.0
        zscore = 0.0
        volatility = 0.0
        rel_volume = 0.0

    brief_md = f"""# Research Brief: {strategy_name.replace('_', ' ').title()} ({symbol})

## 1. Thesis & Hypothesis
- **Strategy Family**: {strategy_name}
- **Asset class**: Crypto Perp ({symbol})
- **Underlying Hypothesis**: Evaluates directional movement based on indicators. MACD indicates trend continuation; Bollinger bands signify breakout opportunities.

## 2. Quantitative Evidence
- **Historical Net PnL**: ${net_pnl:,.2f}
- **Win Rate**: {win_rate:.1f}%
- **Current Market Regime**: {regime} (confidence: {confidence:.2f})
- **Active Indicators**: Z-Score ({zscore:.4f}), Volatility ({volatility:.4f}), Relative Volume ({rel_volume:.4f}).

## 3. Risk & Guardrails Checklist
- **Code Quality Check**: {"PASSED" if code_valid else "FAILED"}
- **Decay Detection status**: {"DECAY DETECTED" if decay_detected else "STABLE"}
- **Overall Gating status**: {"READY" if validation.get('execution_ready') else "WAITING"}

## 4. GO/NOGO Decision Checklist
- [ ] Are transaction fees (5 bps maker/taker) accurately modeled for current volume tier?
- [ ] Is there structural divergence or high macro event risk (e.g. FOMC) within 4 hours?
- [ ] Have parameter thresholds been calibrated within the last 30 days?
"""
    
    feedback = None
    db_dir = Path(db.DB_PATH).parent
    fb_dir = db_dir / 'research_briefs'
    fb_path = fb_dir / f'{symbol}_{strategy_name}_feedback.json'
    if fb_path.exists():
        try:
            feedback = json.loads(fb_path.read_text(encoding='utf-8'))
        except Exception:
            pass
            
    return {
        'symbol': symbol,
        'strategy_name': strategy_name,
        'brief_md': brief_md,
        'feedback': feedback
    }


@router.post('/research-brief/{symbol}/{strategy_name}/feedback')
def post_research_brief_feedback(symbol: str, strategy_name: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    comments = payload.get('comments', '')
    decision = payload.get('decision', 'STANDBY')
    
    db_dir = Path(db.DB_PATH).parent
    fb_dir = db_dir / 'research_briefs'
    fb_dir.mkdir(parents=True, exist_ok=True)
    fb_path = fb_dir / f'{symbol}_{strategy_name}_feedback.json'
    
    fb_data = {
        'symbol': symbol,
        'strategy_name': strategy_name,
        'comments': comments,
        'decision': decision,
        'updated_at': datetime.now().isoformat()
    }
    fb_path.write_text(json.dumps(fb_data, ensure_ascii=False, indent=2), encoding='utf-8')
    
    lane = 'pending_review'
    if decision == 'AUTO_PROMOTE':
        lane = 'promote'
    elif decision == 'AUTO_REVISE':
        lane = 'revise'
    elif decision == 'STANDBY':
        lane = 'qualify'
        
    try:
        path = registry.playbook_file
        if path.exists():
            lines = []
            updated = False
            with path.open('r', encoding='utf-8') as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if data.get('symbol') == symbol and data.get('signal_name') == strategy_name:
                            data['research_status'] = lane
                            data['current_stage'] = lane
                            updated = True
                        lines.append(data)
                    except Exception:
                        pass
            
            if not updated:
                lines.append({
                    'symbol': symbol,
                    'signal_name': strategy_name,
                    'current_stage': lane,
                    'research_status': lane,
                    'timestamp': datetime.now().isoformat()
                })
                
            with path.open('w', encoding='utf-8') as fh:
                for item in lines:
                    fh.write(json.dumps(item) + '\n')
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to update playbook packet stage: {e}")
        
    return {
        'status': 'success',
        'decision': decision,
        'lane': lane,
        'feedback': fb_data
    }
