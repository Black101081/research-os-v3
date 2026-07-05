from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Body
from research_brief_generator import generate_playbook_code
from routers.presets import get_presets

router = APIRouter(prefix="/api")

@router.post('/export-playbook/{symbol}/{strategy_name}')
def post_export_playbook(symbol: str, strategy_name: str, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    parameters = payload.get('parameters', {})
    risk_limit = payload.get('risk_limit', {})
    
    if not parameters or not risk_limit:
        presets = get_presets()
        for p in presets:
            if p.get('spec', {}).get('strategy_family') == strategy_name:
                if not parameters:
                    parameters = p['spec'].get('parameters', {})
                if not risk_limit:
                    risk_limit = p['spec'].get('risk_limit', {})
                    
    if not parameters:
        parameters = {'period': 20, 'std_dev': 2.0}
    if not risk_limit:
        risk_limit = {'max_leverage': 2.0, 'max_exposure_usd': 5000.0, 'stop_loss_pct': 0.015, 'take_profit_pct': 0.03}
        
    code = generate_playbook_code(symbol, strategy_name, parameters, risk_limit)
    
    playbook_dir = Path('data/playbooks')
    playbook_dir.mkdir(parents=True, exist_ok=True)
    playbook_path = playbook_dir / f'{symbol}_{strategy_name}_playbook.py'
    playbook_path.write_text(code, encoding='utf-8')
    
    spec_path = playbook_dir / f'{symbol}_{strategy_name}_spec.json'
    spec_data = {
        'symbol': symbol,
        'strategy_family': strategy_name,
        'parameters': parameters,
        'risk_limit': risk_limit,
        'exported_at': datetime.now().isoformat()
    }
    spec_path.write_text(json.dumps(spec_data, ensure_ascii=False, indent=2), encoding='utf-8')
    
    return {
        'status': 'success',
        'file_path': str(playbook_path),
        'spec_path': str(spec_path),
        'code': code
    }
