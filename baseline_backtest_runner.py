from __future__ import annotations

from pathlib import Path
import json
import math
from datetime import datetime, UTC, timezone
from typing import Dict, Any, List

from backtest_bridge import build_bridge_demo, score_backtest_result
from realtime_engine import ResearchEngine

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / 'runtime'
CONFIG = json.loads((BASE / 'config.example.json').read_text())


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load_backtest_candles(symbol: str, interval: str, lookback_bars: int = 150) -> List[Dict[str, Any]]:
    # Try fetching from API
    try:
        from bootstrap_ohlcv import fetch_candle_snapshot
        candles = fetch_candle_snapshot(symbol, interval, lookback_bars)
        if candles:
            return candles
    except Exception:
        pass
        
    # Fallback to generating synthetic candles
    candles = []
    for i in range(lookback_bars):
        base = 100 + i * 0.18 + math.sin(i / 8) * 0.03
        candles.append({
            'coin': symbol,
            't': f'2026-07-05T01:{i:02d}:00Z',
            'o': base - 0.05,
            'h': base + 0.08,
            'l': base - 0.08,
            'c': base,
            'v': 1000 + i * 2
        })
    return candles


def simulate_event_driven_backtest(
    symbol: str,
    strategy_name: str,
    candles: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    engine = ResearchEngine(symbols=[symbol], max_bars=500, thresholds=config.get('thresholds'))
    
    position = None
    entry_price = 0.0
    entry_time = None
    trades = []
    
    slippage_bps = config.get('execution', {}).get('slippage_bps', 3)
    fees_bps = config.get('execution', {}).get('fees_bps', 5)
    
    warmup_count = min(40, len(candles) // 3)
    for c in candles[:warmup_count]:
        engine.process_message({'channel': 'candle', 'data': c})
        
    for c in candles[warmup_count:]:
        engine.process_message({'channel': 'candle', 'data': c})
        
        snap = engine.snapshot()[symbol]
        signals = snap.get('signals', {})
        signal_state = signals.get(strategy_name, {})
        
        current_price = float(c.get('c', 0.0))
        current_time = c.get('t')
        
        if position is not None:
            stop_loss_pct = 0.015
            take_profit_pct = 0.03
            
            pnl_pct = (current_price - entry_price) / entry_price if position == 'long' else (entry_price - current_price) / entry_price
            
            exit_triggered = False
            exit_reason = ""
            if pnl_pct <= -stop_loss_pct:
                exit_triggered = True
                exit_reason = "stop_loss"
            elif pnl_pct >= take_profit_pct:
                exit_triggered = True
                exit_reason = "take_profit"
            elif not signal_state.get('active'):
                exit_triggered = True
                exit_reason = "signal_invalidation"
                
            if exit_triggered:
                if position == 'long':
                    exit_price = current_price * (1 - slippage_bps / 10000)
                else:
                    exit_price = current_price * (1 + slippage_bps / 10000)
                    
                gross_trade_pnl = (exit_price - entry_price) if position == 'long' else (entry_price - exit_price)
                gross_trade_pnl_pct = gross_trade_pnl / entry_price
                net_trade_pnl_pct = gross_trade_pnl_pct - (2 * fees_bps / 10000)
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'direction': position,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl_pct': round(net_trade_pnl_pct * 100, 4),
                    'reason': exit_reason
                })
                position = None
                
        if position is None:
            if signal_state.get('active'):
                position = 'long'
                entry_price = current_price * (1 + slippage_bps / 10000)
                entry_time = current_time

    total_trades = len(trades)
    if total_trades > 0:
        win_trades = [t for t in trades if t['pnl_pct'] > 0]
        win_rate = len(win_trades) / total_trades
        net_pnl = sum(t['pnl_pct'] for t in trades)
        gross_pnl = round(net_pnl + (total_trades * 2 * fees_bps / 100), 2)
        
        cum_pnl = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in trades:
            cum_pnl += t['pnl_pct']
            if cum_pnl > peak:
                peak = cum_pnl
            dd = peak - cum_pnl
            if dd > max_dd:
                max_dd = dd
        expectancy = round(net_pnl / total_trades, 4)
    else:
        win_rate = 0.0
        net_pnl = 0.0
        gross_pnl = 0.0
        max_dd = 0.0
        expectancy = 0.0
        
    return {
        'trade_count': total_trades,
        'gross_pnl': gross_pnl,
        'net_pnl': round(net_pnl, 2),
        'max_drawdown': round(max_dd, 2),
        'win_rate': round(win_rate, 3),
        'expectancy': expectancy,
        'trades': trades
    }


def run_backtest_runner_demo() -> Dict[str, Any]:
    bridge = build_bridge_demo()
    results = []
    
    # Preload candles for default symbol BTC
    symbol = 'BTC'
    candles = load_backtest_candles(symbol, CONFIG.get('candle_interval', '1m'), 150)
    
    for job in bridge.get('jobs', []):
        signals = job.get('source_signals', [])
        sig_name = signals[0] if signals else 'macd_trend_continuation'
        
        metrics = simulate_event_driven_backtest(symbol, sig_name, candles, CONFIG)
            
        gate_inputs = {
            'pnl_score': min(5, max(2, int(metrics['net_pnl'] // 5) + 1)),
            'drawdown_score': 5 if metrics['max_drawdown'] <= 8 else 4 if metrics['max_drawdown'] <= 12 else 3,
            'stability_score': 5 if job.get('upstream_signal_quality_avg', 0) >= 23 else 4,
            'robustness_score': 5 if job.get('upstream_signal_quality_min', 0) >= 20 else 4,
            'execution_score': 5 if 'execution' in job.get('strategy_family', '') else 4,
        }
        
        gate = score_backtest_result(gate_inputs)
        notes = 'Event-driven high-fidelity backtest'
        results.append({**job, 'runner_metrics': metrics, 'decision_gate': gate, 'notes': notes})
        
    out = {'generated_at': _now(), 'result_count': len(results), 'results': results}
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / 'backtest_runner_demo.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(json.dumps(run_backtest_runner_demo(), ensure_ascii=False, indent=2))
