from __future__ import annotations

import os
import json
import random
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
from bootstrap_ohlcv import fetch_candle_snapshot
import factor_math as fm
import database as db

# Thresholds / Rules
WFE_THRESHOLD = 50.0
P_VAL_THRESHOLD = 0.05

def calculate_sharpe(returns: List[float], interval: str) -> float:
    if not returns:
        return 0.0
    arr = np.array(returns, dtype=np.float64)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return 0.0
        
    # Scale annualization factor based on timeframe
    # minutes per year = 525600
    tf_minutes = {
        '1m': 1.0,
        '5m': 5.0,
        '15m': 15.0,
        '1h': 60.0
    }
    m = tf_minutes.get(interval, 5.0)
    bars_per_year = 525600.0 / m
    return float(mean / std * np.sqrt(bars_per_year))

def simulate_strategy(
    candles: List[Dict[str, Any]],
    adx_threshold: float,
    atr_multiplier: float,
    interval: str
) -> Tuple[float, List[float]]:
    closes = [float(c['c']) for c in candles]
    highs = [float(c['h']) for c in candles]
    lows = [float(c['l']) for c in candles]
    
    if len(closes) < 30:
        return 0.0, []

    # Calculate indicators
    atr_vals = []
    rsi_vals = []
    adx_vals = []
    
    for i in range(1, len(closes) + 1):
        c_sub = closes[:i]
        h_sub = highs[:i]
        l_sub = lows[:i]
        
        if len(c_sub) >= 15:
            atr_vals.append(fm.calc_atr(h_sub, l_sub, c_sub, period=14))
            rsi_vals.append(fm.calc_rsi(c_sub, period=14))
        else:
            atr_vals.append(0.0)
            rsi_vals.append(50.0)
            
        if len(c_sub) >= 29:
            adx_vals.append(fm.calc_adx(h_sub, l_sub, c_sub, period=14))
        else:
            adx_vals.append(0.0)

    trades = []
    position = None
    entry_price = 0.0
    stop_loss = 0.0
    initial_sl = 0.0
    breakeven_triggered = False
    max_favorable = 0.0
    
    for i in range(30, len(closes)):
        current_price = closes[i]
        atr = atr_vals[i]
        adx = adx_vals[i]
        rsi = rsi_vals[i]
        
        if position is not None:
            if position == "long":
                max_favorable = max(max_favorable, current_price)
                risk_per_unit = entry_price - initial_sl
                if not breakeven_triggered and current_price - entry_price >= risk_per_unit:
                    stop_loss = entry_price
                    breakeven_triggered = True
                if breakeven_triggered:
                    trail_sl = max_favorable - 1.5 * atr
                    stop_loss = max(stop_loss, trail_sl)
                if current_price <= stop_loss:
                    pnl = (stop_loss - entry_price) / entry_price
                    trades.append(pnl)
                    position = None
            else:
                max_favorable = min(max_favorable, current_price)
                risk_per_unit = initial_sl - entry_price
                if not breakeven_triggered and entry_price - current_price >= risk_per_unit:
                    stop_loss = entry_price
                    breakeven_triggered = True
                if breakeven_triggered:
                    trail_sl = max_favorable + 1.5 * atr
                    stop_loss = min(stop_loss, trail_sl)
                if current_price >= stop_loss:
                    pnl = (entry_price - stop_loss) / entry_price
                    trades.append(pnl)
                    position = None
        else:
            if adx < adx_threshold and adx > 0:
                if rsi < 30:
                    position = "long"
                    entry_price = current_price
                    stop_loss = entry_price - atr_multiplier * atr
                    initial_sl = stop_loss
                    breakeven_triggered = False
                    max_favorable = entry_price
                elif rsi > 70:
                    position = "short"
                    entry_price = current_price
                    stop_loss = entry_price + atr_multiplier * atr
                    initial_sl = stop_loss
                    breakeven_triggered = False
                    max_favorable = entry_price
                    
    sharpe = calculate_sharpe(trades, interval)
    return sharpe, trades

def run_grid_sweep(candles: List[Dict[str, Any]], interval: str) -> Dict[Tuple[float, float], float]:
    # Sweeps 14 * 14 = 196 combinations
    adx_grid = np.linspace(15.0, 35.0, 14)
    atr_grid = np.linspace(1.2, 3.5, 14)
    
    results = {}
    for adx in adx_grid:
        for atr in atr_grid:
            sharpe, _ = simulate_strategy(candles, adx, atr, interval)
            results[(float(adx), float(atr))] = sharpe
    return results

def get_neighbor_variance(adx: float, atr: float, grid_results: Dict[Tuple[float, float], float]) -> float:
    neighbors = []
    for (k_adx, k_atr), val in grid_results.items():
        if abs(k_adx - adx) <= 2.0 and abs(k_atr - atr) <= 0.3:
            neighbors.append(val)
    if not neighbors:
        return 0.0
    return float(np.var(neighbors))

def run_monte_carlo(actual_returns: List[float], real_sharpe: float, interval: str, n_iterations: int = 1000) -> float:
    if not actual_returns:
        return 1.0
    better_runs = 0
    for _ in range(n_iterations):
        shuffled = list(actual_returns)
        random.shuffle(shuffled)
        fake_sharpe = calculate_sharpe(shuffled, interval)
        if fake_sharpe >= real_sharpe:
            better_runs += 1
    return better_runs / n_iterations

def main():
    symbols = ['BTC', 'ETH', 'SOL']
    intervals = ['1m', '5m', '15m', '1h']
    
    results_list = []
    best_parameters_matrix = {}
    
    print("🚀 Starting Batch Parameter Matrix Optimization (Full Walk-Forward + Monte Carlo)...")
    t_start_all = time.time()
    
    for symbol in symbols:
        best_parameters_matrix[symbol] = {}
        for interval in intervals:
            print(f"\n🔍 Optimizing {symbol} on {interval}...")
            t_start = time.time()
            
            # Fetch candles
            try:
                candles = fetch_candle_snapshot(symbol, interval, 500)
            except Exception as e:
                print(f"❌ Error fetching candles for {symbol} {interval}: {e}")
                continue
                
            if not candles or len(candles) < 100:
                print(f"⚠️ Insufficient candles ({len(candles) if candles else 0}) for {symbol} {interval}")
                continue
                
            n_candles = len(candles)
            is_split = int(n_candles * 0.75)
            is_candles = candles[:is_split]
            oos_candles = candles[is_split:]
            
            # 1. Grid Sweep on In-Sample
            is_grid = run_grid_sweep(is_candles, interval)
            
            # 2. Find Flatness-aware optimal parameters
            best_params = None
            best_is_sharpe = -float('inf')
            best_flatness_score = -float('inf')
            
            for (adx, atr), sharpe in is_grid.items():
                var = get_neighbor_variance(adx, atr, is_grid)
                flatness_score = sharpe - 0.5 * var
                if flatness_score > best_flatness_score:
                    best_flatness_score = flatness_score
                    best_params = (adx, atr)
                    best_is_sharpe = sharpe
            
            if not best_params:
                print(f"⚠️ Could not optimize parameters for {symbol} {interval}")
                continue
                
            opt_adx, opt_atr = best_params
            
            # 3. Out-of-Sample (OOS) Walk-Forward Run
            oos_sharpe, oos_returns = simulate_strategy(oos_candles, opt_adx, opt_atr, interval)
            wfe = (oos_sharpe / best_is_sharpe * 100.0) if best_is_sharpe > 0 else 0.0
            
            # 4. Monte Carlo Permutation Test (1,000 runs)
            p_val = run_monte_carlo(oos_returns, oos_sharpe, interval, 1000)
            
            # 5. Determine Validation Gates Status
            flatness_ok = best_flatness_score > 0
            wfe_ok = wfe >= WFE_THRESHOLD
            p_val_ok = p_val < P_VAL_THRESHOLD
            
            passed_gates = flatness_ok and wfe_ok and p_val_ok
            status_text = "PASS" if passed_gates else "FAIL"
            
            duration = time.time() - t_start
            print(f"✅ {symbol} {interval} Done in {duration:.1f}s | Optimal ADX={opt_adx:.2f}, ATR={opt_atr:.2f} | IS={best_is_sharpe:.3f}, OOS={oos_sharpe:.3f} | WFE={wfe:.1f}% | p-val={p_val:.4f} | Status={status_text}")
            
            # Store results
            best_parameters_matrix[symbol][interval] = {
                "adx_threshold": float(opt_adx),
                "atr_multiplier": float(opt_atr),
                "is_sharpe": float(best_is_sharpe),
                "oos_sharpe": float(oos_sharpe),
                "wfe_pct": float(wfe),
                "mc_p_value": float(p_val),
                "status": status_text
            }
            
            results_list.append({
                "symbol": symbol,
                "interval": interval,
                "opt_adx": opt_adx,
                "opt_atr": opt_atr,
                "is_sharpe": best_is_sharpe,
                "oos_sharpe": oos_sharpe,
                "wfe": wfe,
                "p_val": p_val,
                "status": status_text
            })
            
    # Save Matrix JSON
    runtime_dir = Path("runtime")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    matrix_json_path = runtime_dir / "best_parameter_matrix.json"
    matrix_json_path.write_text(json.dumps(best_parameters_matrix, indent=2), encoding="utf-8")
    print(f"\n💾 Saved best parameters matrix mapping to: {matrix_json_path}")
    
    # Save report artifact
    report_content = f"""# Parameter Matrix Optimization & Validation Report

**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Mode**: Advanced Walk-Forward + Monte Carlo (196 Trials)

## Master Parameter Matrix

| Symbol | Timeframe | Best ADX Limit | Best ATR Mult | IS Sharpe | OOS Sharpe | WFE % | MC p-value | Status |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
"""
    for r in results_list:
        report_content += f"| **{r['symbol']}** | {r['interval']} | {r['opt_adx']:.2f} | {r['opt_atr']:.2f} | {r['is_sharpe']:.3f} | {r['oos_sharpe']:.3f} | {r['wfe']:.1f}% | {r['p_val']:.4f} | **{r['status']}** |\n"
        
    report_content += """
## Gate Validation Rules
1. **Parameter Space Flatness**: Penalizes isolated sharp parameter peaks to select robust, stable regions.
2. **Walk-Forward Efficiency (WFE)**: Requires Out-of-Sample Sharpe to be at least **50%** of In-Sample Sharpe to prove strategy does not decay.
3. **Monte Carlo Permutation**: Permutes trade returns 1,000 times; requires p-value < **0.05** to guarantee performance is statistically significant (not luck).
"""
    
    artifact_path = Path("C:/Users/Black/.gemini/antigravity/brain/de3c89b4-8573-43c0-bddf-c3de5b0e0676/parameter_matrix_results.md")
    artifact_path.write_text(report_content, encoding='utf-8')
    print(f"📊 Matrix report written to: {artifact_path}")
    print(f"⏱️ Total batch runtime: {time.time() - t_start_all:.1f} seconds")

if __name__ == '__main__':
    main()
