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


def simulate_event_driven_backtest_multi(
    symbol: str,
    strategy_names: List[str],
    candles: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    engine = ResearchEngine(symbols=[symbol], max_bars=500, thresholds=config.get('thresholds'))
    
    positions = {name: None for name in strategy_names}
    entry_prices = {name: 0.0 for name in strategy_names}
    stop_losses = {name: 0.0 for name in strategy_names}
    take_profits = {name: 0.0 for name in strategy_names}
    entry_times = {name: None for name in strategy_names}
    trades_dict = {name: [] for name in strategy_names}
    
    slippage_bps = config.get('execution', {}).get('slippage_bps', 3)
    fees_bps = config.get('execution', {}).get('fees_bps', 5)
    
    warmup_count = min(40, len(candles) // 3)
    for c in candles[:warmup_count]:
        engine.process_message({'channel': 'candle', 'data': c})
        
    for idx, c in enumerate(candles[warmup_count:]):
        if idx % 1000 == 0:
            print(f"  Processed {idx}/{len(candles)-warmup_count} candles...")
        engine.process_message({'channel': 'candle', 'data': c})
        
        snap = engine.snapshot()[symbol]
        signals = snap.get('signals', {})
        
        current_price = float(c.get('c', 0.0))
        current_time = c.get('t')
        
        for name in strategy_names:
            signal_state = signals.get(name, {})
            position = positions[name]
            
            if position is not None:
                pnl_pct = (current_price - entry_prices[name]) / entry_prices[name] if position == 'long' else (entry_prices[name] - current_price) / entry_prices[name]
                
                exit_triggered = False
                exit_reason = ""
                
                if position == 'long':
                    if current_price <= stop_losses[name]:
                        exit_triggered = True
                        exit_reason = "stop_loss"
                    elif current_price >= take_profits[name]:
                        exit_triggered = True
                        exit_reason = "take_profit"
                else:
                    if current_price >= stop_losses[name]:
                        exit_triggered = True
                        exit_reason = "stop_loss"
                    elif current_price <= take_profits[name]:
                        exit_triggered = True
                        exit_reason = "take_profit"
                        
                if not exit_triggered and not signal_state.get('active'):
                    exit_triggered = True
                    exit_reason = "signal_invalidation"
                    
                if exit_triggered:
                    if position == 'long':
                        exit_price = current_price * (1 - slippage_bps / 10000)
                    else:
                        exit_price = current_price * (1 + slippage_bps / 10000)
                        
                    gross_trade_pnl = (exit_price - entry_prices[name]) if position == 'long' else (entry_prices[name] - exit_price)
                    gross_trade_pnl_pct = gross_trade_pnl / entry_prices[name]
                    net_trade_pnl_pct = gross_trade_pnl_pct - (2 * fees_bps / 10000)
                    
                    trades_dict[name].append({
                        'entry_time': entry_times[name],
                        'exit_time': current_time,
                        'direction': position,
                        'entry_price': entry_prices[name],
                        'exit_price': exit_price,
                        'pnl_pct': round(net_trade_pnl_pct * 100, 4),
                        'reason': exit_reason
                    })
                    positions[name] = None
                    
            if positions[name] is None:
                if signal_state.get('active'):
                    from realtime_engine import _infer_entry_side
                    pos_side = _infer_entry_side(
                        name, 
                        current_price, 
                        snap.get('indicators', {}), 
                        signal_state.get('template_family')
                    )
                    positions[name] = pos_side
                    
                    tf_indicators = snap.get('indicators', {})
                    atr_val = tf_indicators.get('atr_pct_14', 0.02)
                    sl_pct = max(0.01, atr_val * 1.5)
                    
                    bb_width = tf_indicators.get('BollingerWidth', 0.03)
                    tp_pct = max(0.01, bb_width)
                    
                    if pos_side == 'long':
                        entry_prices[name] = current_price * (1 + slippage_bps / 10000)
                        stop_losses[name] = entry_prices[name] * (1 - sl_pct)
                        take_profits[name] = entry_prices[name] * (1 + tp_pct)
                    else:
                        entry_prices[name] = current_price * (1 - slippage_bps / 10000)
                        stop_losses[name] = entry_prices[name] * (1 + sl_pct)
                        take_profits[name] = entry_prices[name] * (1 - tp_pct)
                        
                    entry_times[name] = current_time
                    
    # Calculate metrics for each strategy
    all_metrics = {}
    for name in strategy_names:
        trades = trades_dict[name]
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
            
        all_metrics[name] = {
            'trade_count': total_trades,
            'gross_pnl': gross_pnl,
            'net_pnl': round(net_pnl, 2),
            'max_drawdown': round(max_dd, 2),
            'win_rate': round(win_rate, 3),
            'expectancy': expectancy,
            'trades': trades
        }
    return all_metrics


def run_backtest_runner_demo() -> Dict[str, Any]:
    from alpha_factory_runner import AlphaFactoryRunner
    
    RUNTIME.mkdir(exist_ok=True)
    factory = AlphaFactoryRunner(store_base=RUNTIME / 'alpha_registry_data')
    
    symbol = 'BTC'
    candles = load_backtest_candles(symbol, CONFIG.get('candle_interval', '1m'), 5000)
    
    signals_to_test = [
        "signal_macd_continuation",
        "signal_rsi_divergence",
        "signal_bb_squeeze_breakout",
        "signal_mean_reversion",
        "signal_order_flow_imbalance",
        "signal_volatility_event",
        "signal_funding_reversion",
        "signal_oi_reversal"
    ]
    
    print(f"Running optimized single-pass backtest for {len(signals_to_test)} strategies on {len(candles)} candles...")
    multi_metrics = simulate_event_driven_backtest_multi(symbol, signals_to_test, candles, CONFIG)
    
    results = []
    for sig_name in signals_to_test:
        metrics = multi_metrics[sig_name]
            
        gate_inputs = {
            'pnl_score': min(5, max(2, int(metrics['net_pnl'] // 5) + 1)),
            'drawdown_score': 5 if metrics['max_drawdown'] <= 8 else 4 if metrics['max_drawdown'] <= 12 else 3,
            'stability_score': 4,
            'robustness_score': 4,
            'execution_score': 4,
        }
        
        if metrics['net_pnl'] > 0 and metrics['max_drawdown'] < 15.0:
            decision = 'promote'
            
            from alpha_registry import now_iso
            payload = {
                'alpha_id': f"alpha_{sig_name}_{symbol}",
                'alpha_name': f"Alpha {sig_name.replace('signal_', '').replace('_', ' ').title()}",
                'source_type': 'auto_backtest',
                'symbol_scope': [symbol],
                'universe_scope': ['major'],
                'timeframe': CONFIG.get('candle_interval', '1m'),
                'regime_scope': ['trend', 'mean_reverting', 'volatile'],
                'factor_dependencies': [],
                'indicator_dependencies': [],
                'signal_template_family': sig_name.replace('signal_', ''),
                'signal_expression': '',
                'parameter_set': {'slippage_bps': 3, 'fees_bps': 5},
                'thesis_summary': f"Auto-discovered via event-driven backtest. Net PnL: {metrics['net_pnl']:.2f}%",
                'created_at': now_iso(),
                'created_by': 'AlphaFactory'
            }
            factory.registry.add_alpha_definition(payload)
            factory.store.append('alpha_definitions', payload)
        else:
            decision = 'reject'
        
        gate = {'decision': decision, 'backtest_score_total': sum(gate_inputs.values())}
        notes = f"Auto backtest: PnL {metrics['net_pnl']}%, MaxDD {metrics['max_drawdown']}%"
        
        job = {
            'job_id': f"bt_{sig_name}",
            'strategy_family': sig_name.replace('signal_', ''),
            'source_signals': [sig_name],
        }
        results.append({**job, 'runner_metrics': metrics, 'decision_gate': gate, 'notes': notes})
        
    out = {'generated_at': _now(), 'result_count': len(results), 'results': results}
    (RUNTIME / 'backtest_runner_demo.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(json.dumps(run_backtest_runner_demo(), ensure_ascii=False, indent=2))
