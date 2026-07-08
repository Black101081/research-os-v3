from __future__ import annotations

import os
import random
import numpy as np
from typing import List, Dict, Any, Tuple
from pathlib import Path
from bootstrap_ohlcv import fetch_candle_snapshot
import factor_math as fm

def calculate_sharpe(returns: List[float]) -> float:
    if not returns:
        return 0.0
    arr = np.array(returns, dtype=np.float64)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return 0.0
    # Annualized Sharpe ratio assuming 5m intervals
    # 5m bars per year = 12 * 24 * 365 = 105120
    return float(mean / std * np.sqrt(105120))

def simulate_strategy(
    candles: List[Dict[str, Any]],
    adx_threshold: float,
    atr_multiplier: float
) -> Tuple[float, List[float]]:
    """Simulates a simple mean-reversion strategy with dynamic trailing stop-loss."""
    closes = [float(c['c']) for c in candles]
    highs = [float(c['h']) for c in candles]
    lows = [float(c['l']) for c in candles]
    
    if len(closes) < 30:
        return 0.0, []

    # Calculate indicators
    atr_vals = []
    adx_vals = []
    rsi_vals = []
    
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
            # Update max favorable price
            if position == "long":
                max_favorable = max(max_favorable, current_price)
                risk_per_unit = entry_price - initial_sl
                # Breakeven trigger
                if not breakeven_triggered and current_price - entry_price >= risk_per_unit:
                    stop_loss = entry_price
                    breakeven_triggered = True
                # Trailing step
                if breakeven_triggered:
                    trail_sl = max_favorable - 1.5 * atr
                    stop_loss = max(stop_loss, trail_sl)
                # Check exit
                if current_price <= stop_loss:
                    pnl = (stop_loss - entry_price) / entry_price
                    trades.append(pnl)
                    position = None
            else:
                max_favorable = min(max_favorable, current_price)
                risk_per_unit = initial_sl - entry_price
                # Breakeven trigger
                if not breakeven_triggered and entry_price - current_price >= risk_per_unit:
                    stop_loss = entry_price
                    breakeven_triggered = True
                # Trailing step
                if breakeven_triggered:
                    trail_sl = max_favorable + 1.5 * atr
                    stop_loss = min(stop_loss, trail_sl)
                # Check exit
                if current_price >= stop_loss:
                    pnl = (entry_price - stop_loss) / entry_price
                    trades.append(pnl)
                    position = None
        else:
            # Entry logic: Buy/Sell on RSI extreme if ADX is below threshold (ranging market)
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
                    
    sharpe = calculate_sharpe(trades)
    return sharpe, trades

def run_grid_sweep(candles: List[Dict[str, Any]]) -> Dict[Tuple[float, float], float]:
    adx_grid = [18.0, 22.0, 25.0, 28.0, 32.0]
    atr_grid = [1.5, 1.8, 2.0, 2.5, 3.0]
    
    results = {}
    for adx in adx_grid:
        for atr in atr_grid:
            sharpe, _ = simulate_strategy(candles, adx, atr)
            results[(adx, atr)] = sharpe
    return results

def get_neighbor_variance(adx: float, atr: float, grid_results: Dict[Tuple[float, float], float]) -> float:
    # Neighbors within +/- 5 for ADX and +/- 0.5 for ATR
    neighbors = []
    for (k_adx, k_atr), val in grid_results.items():
        if abs(k_adx - adx) <= 5.0 and abs(k_atr - atr) <= 0.6:
            neighbors.append(val)
    if not neighbors:
        return 0.0
    return float(np.var(neighbors))

def run_monte_carlo(actual_returns: List[float], real_sharpe: float, n_iterations: int = 1000) -> float:
    if not actual_returns:
        return 1.0
    better_runs = 0
    for _ in range(n_iterations):
        shuffled = list(actual_returns)
        random.shuffle(shuffled)
        fake_sharpe = calculate_sharpe(shuffled)
        if fake_sharpe >= real_sharpe:
            better_runs += 1
    return better_runs / n_iterations

def main():
    print("[Optimizer] Fetching candles for BTC...")
    candles = fetch_candle_snapshot("BTC", "5m", 500)
    if not candles:
        print("[Error] Could not fetch candles.")
        return
        
    n_candles = len(candles)
    is_split = int(n_candles * 0.75)
    
    is_candles = candles[:is_split]
    oos_candles = candles[is_split:]
    
    print(f"[Optimizer] Data Split: In-Sample={len(is_candles)} bars, Out-of-Sample={len(oos_candles)} bars")
    
    # 1. Grid Sweep on In-Sample
    print("[Optimizer] Running Grid Sweep on In-Sample data...")
    is_grid = run_grid_sweep(is_candles)
    
    # 2. Find Flatness-aware Optimal Parameters
    best_params = None
    best_score = -float('inf')
    best_flatness_score = -float('inf')
    
    flatness_report = []
    
    for (adx, atr), sharpe in is_grid.items():
        var = get_neighbor_variance(adx, atr, is_grid)
        # Flatness score = Sharpe - 0.5 * Neighbor Variance (penalize isolated spikes)
        flatness_score = sharpe - 0.5 * var
        flatness_report.append((adx, atr, sharpe, var, flatness_score))
        
        if flatness_score > best_flatness_score:
            best_flatness_score = flatness_score
            best_params = (adx, atr)
            best_score = sharpe
            
    print(f"[Optimizer] Selected Flatness-aware Parameters: ADX={best_params[0]}, ATR Mult={best_params[1]}")
    print(f"            IS Sharpe: {best_score:.4f} (Flatness Score: {best_flatness_score:.4f})")
    
    # 3. Walk-Forward Run (Out-of-Sample)
    print("[Optimizer] Running Optimal Parameters on Out-of-Sample data...")
    oos_sharpe, oos_returns = simulate_strategy(oos_candles, best_params[0], best_params[1])
    
    wfe = (oos_sharpe / best_score * 100.0) if best_score > 0 else 0.0
    print(f"[Optimizer] OOS Sharpe: {oos_sharpe:.4f} | Walk-Forward Efficiency (WFE): {wfe:.2f}%")
    
    # 4. Monte Carlo Permutation Test
    print("[Optimizer] Running Monte Carlo Permutation Test (1,000 iterations)...")
    p_val = run_monte_carlo(oos_returns, oos_sharpe, 1000)
    print(f"[Optimizer] Monte Carlo p-value: {p_val:.4f}")
    
    # 5. Output Report to Artifact
    report_content = f"""# Walk-Forward Optimization & Anti-Overfitting Validation Report

**Run Date**: 2026-07-08
**Asset**: BTC/USDT (5m)

## Summary results

- **Optimal parameters**: ADX < {best_params[0]} (Range Filter), ATR Multiplier = {best_params[1]}
- **In-Sample (IS) Sharpe Ratio**: {best_score:.4f}
- **Out-of-Sample (OOS) Sharpe Ratio**: {oos_sharpe:.4f}
- **Walk-Forward Efficiency (WFE)**: {wfe:.2f}% (Threshold: > 50%)
- **Monte Carlo p-value**: {p_val:.4f} (Threshold: < 0.05)

## Parameter Space Flatness Report (In-Sample Grid)

| ADX threshold | ATR Mult | Sharpe Ratio | Neighbor Variance | Flatness Score |
|---------------|----------|--------------|-------------------|----------------|
"""
    for adx, atr, sh, var, fs in sorted(flatness_report, key=lambda x: x[4], reverse=True):
        report_content += f"| {adx:<13} | {atr:<8} | {sh:<12.4f} | {var:<17.4f} | {fs:<14.4f} |\n"
        
    report_content += f"""
## Anti-Overfitting Gateways Validation Status

- **Parameter Flatness Gate**: {"PASS" if best_flatness_score > 0 else "FAIL"} (Variance penalized selection)
- **Walk-Forward Gate**: {"PASS" if wfe >= 50.0 else "FAIL"} (WFE = {wfe:.2f}% vs 50.0% threshold)
- **Monte Carlo Gate**: {"PASS" if p_val < 0.05 else "FAIL"} (p-value = {p_val:.4f} vs 0.05 threshold)
"""
    
    report_path = Path("C:/Users/Black/.gemini/antigravity/brain/de3c89b4-8573-43c0-bddf-c3de5b0e0676/optimization_results.md")
    report_path.write_text(report_content, encoding='utf-8')
    print(f"[Optimizer] Report written to: {report_path}")

if __name__ == "__main__":
    main()
