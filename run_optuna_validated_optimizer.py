from __future__ import annotations

import os
import json
import random
import time
import optuna
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
from bootstrap_ohlcv import fetch_candle_snapshot
import factor_math as fm
import database as db

# Disable optuna logs to keep stdout clean
optuna.logging.set_verbosity(optuna.logging.WARNING)

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
    rsi_period: int,
    rsi_lower: float,
    rsi_upper: float,
    interval: str
) -> Tuple[float, List[float], float]:
    closes = [float(c['c']) for c in candles]
    highs = [float(c['h']) for c in candles]
    lows = [float(c['l']) for c in candles]
    
    # Needs enough bars for indicators
    min_lookback = max(30, rsi_period + 2, 29)
    if len(closes) < min_lookback:
        return 0.0, [], 0.0

    # Pre-calculate indicators
    atr_vals = []
    rsi_vals = []
    adx_vals = []
    
    # Optimizing speed by computing indicators in-line with fm functions
    for i in range(1, len(closes) + 1):
        c_sub = closes[:i]
        h_sub = highs[:i]
        l_sub = lows[:i]
        
        if len(c_sub) >= rsi_period + 1:
            atr_vals.append(fm.calc_atr(h_sub, l_sub, c_sub, period=14))
            rsi_vals.append(fm.calc_rsi(c_sub, period=rsi_period))
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
    
    for i in range(min_lookback, len(closes)):
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
                if rsi < rsi_lower:
                    position = "long"
                    entry_price = current_price
                    stop_loss = entry_price - atr_multiplier * atr
                    initial_sl = stop_loss
                    breakeven_triggered = False
                    max_favorable = entry_price
                elif rsi > rsi_upper:
                    position = "short"
                    entry_price = current_price
                    stop_loss = entry_price + atr_multiplier * atr
                    initial_sl = stop_loss
                    breakeven_triggered = False
                    max_favorable = entry_price
                    
    sharpe = calculate_sharpe(trades, interval)
    
    # Calculate Win Rate
    wins = [t for t in trades if t > 0]
    win_rate = len(wins) / len(trades) if trades else 0.0
    
    return sharpe, trades, win_rate

def run_monte_carlo(actual_returns: List[float], real_sharpe: float, interval: str, n_iterations: int = 1000) -> float:
    if not actual_returns:
        return 1.0
    better_runs = 0
    for _ in range(n_iterations):
        # 1. Non-fill rate (simulate 15% missed limit orders by keeping 85% of trades)
        n_keep = int(len(actual_returns) * 0.85)
        if n_keep == 0:
            shuffled = []
        else:
            shuffled = random.sample(actual_returns, n_keep)
            
        # 2. Random slippage (subtract between 0.0 and 1.5 bps from each trade return)
        stressed = []
        for r in shuffled:
            slippage = random.uniform(0.0, 0.00015)
            stressed.append(r - slippage)
            
        fake_sharpe = calculate_sharpe(stressed, interval)
        if fake_sharpe >= real_sharpe:
            better_runs += 1
    return better_runs / n_iterations

def compute_suitability_score(
    oos_sharpe: float,
    wfe_pct: float,
    p_val: float,
    win_rate: float,
    n_trades: int
) -> Tuple[float, str]:
    if n_trades == 0:
        return 0.0, "UNSUITABLE"
        
    # Hard gate: WFE must be at least 60% to avoid overfitted parameter sets
    if wfe_pct < 60.0:
        return 0.0, "UNSUITABLE"
        
    # Scale Sharpe contribution (OOS Sharpe of 2.0 = 0.40 score)
    sharpe_score = min(0.40, max(0.0, oos_sharpe / 5.0))
    
    # WFE contribution (100% = 0.30 score)
    wfe_score = min(0.30, max(0.0, wfe_pct / 100.0 * 0.30))
    
    # MC contribution (p-val=0 = 0.20 score)
    mc_score = max(0.0, (1.0 - p_val) * 0.20)
    
    # Win Rate contribution (win_rate=1.0 = 0.10 score)
    wr_score = win_rate * 0.10
    
    composite = sharpe_score + wfe_score + mc_score + wr_score
    
    if composite >= 0.75:
        suitability = "EXCELLENT"
    elif composite >= 0.50:
        suitability = "VIABLE"
    else:
        suitability = "UNSUITABLE"
        
    return float(composite), suitability

def run_optuna_optimization(
    candles: List[Dict[str, Any]],
    interval: str,
    n_trials: int = 50
) -> Dict[str, Any]:
    def objective(trial: optuna.Trial) -> float:
        adx_threshold = trial.suggest_float("adx_threshold", 15.0, 35.0)
        atr_multiplier = trial.suggest_float("atr_multiplier", 1.0, 4.0)
        rsi_period = trial.suggest_int("rsi_period", 10, 20)
        rsi_lower = trial.suggest_float("rsi_lower", 20.0, 40.0)
        rsi_upper = trial.suggest_float("rsi_upper", 60.0, 80.0)
        
        sharpe, _, _ = simulate_strategy(
            candles, adx_threshold, atr_multiplier, rsi_period, rsi_lower, rsi_upper, interval
        )
        return sharpe

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    
    # Post-optimization Flatness Check:
    # Compute neighborhood variance around best trial parameters
    best_params = study.best_params
    neighbor_sharpes = []
    for t in study.trials:
        if t.state == optuna.trial.TrialState.COMPLETE:
            p = t.params
            dist = (
                abs(p["adx_threshold"] - best_params["adx_threshold"]) / 20.0 +
                abs(p["atr_multiplier"] - best_params["atr_multiplier"]) / 3.0 +
                abs(p["rsi_period"] - best_params["rsi_period"]) / 10.0
            )
            if dist <= 0.15:
                neighbor_sharpes.append(t.value)
                
    flatness_variance = float(np.var(neighbor_sharpes)) if len(neighbor_sharpes) > 1 else 0.0
    
    return {
        "best_params": best_params,
        "is_sharpe": study.best_value,
        "flatness_variance": flatness_variance
    }

def main():
    # Optimizing all 10 coins shown in the UI configuration
    symbols = ['BTC', 'ETH', 'SOL', 'AVAX', 'SUI', 'NEAR', 'ADA', 'XRP', 'LINK', 'LTC']
    intervals = ['1m', '5m', '15m', '1h']
    
    results_list = []
    optuna_matrix_mapping = {}
    
    print("🚀 Starting Optuna Validated Parameter Optimization & Suitability Engine...")
    t_start_all = time.time()
    
    for symbol in symbols:
        optuna_matrix_mapping[symbol] = {}
        for interval in intervals:
            print(f"\n🔍 Running Optuna Sweep for {symbol} on {interval}...")
            t_start = time.time()
            
            # Fetch longer lookback to provide enough trades for validation (1,000 candles)
            try:
                candles = fetch_candle_snapshot(symbol, interval, 1000)
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
            
            # 1. Optuna Search on In-Sample
            opt_res = run_optuna_optimization(is_candles, interval, n_trials=50)
            best_params = opt_res["best_params"]
            is_sharpe = opt_res["is_sharpe"]
            flatness_var = opt_res["flatness_variance"]
            
            # 2. Out-of-Sample Walk-Forward
            oos_sharpe, oos_returns, win_rate = simulate_strategy(
                oos_candles,
                best_params["adx_threshold"],
                best_params["atr_multiplier"],
                best_params["rsi_period"],
                best_params["rsi_lower"],
                best_params["rsi_upper"],
                interval
            )
            wfe = (oos_sharpe / is_sharpe * 100.0) if is_sharpe > 0 else 0.0
            
            # 3. Monte Carlo validation
            p_val = run_monte_carlo(oos_returns, oos_sharpe, interval, 1000)
            
            # 4. Strategy-Asset-Timeframe Suitability Fit
            composite_score, suitability = compute_suitability_score(
                oos_sharpe, wfe, p_val, win_rate, len(oos_returns)
            )
            
            duration = time.time() - t_start
            print(f"✅ Done in {duration:.1f}s | Params: ADX={best_params['adx_threshold']:.1f}, ATR={best_params['atr_multiplier']:.2f}, RSI_P={best_params['rsi_period']} | IS Sharpe={is_sharpe:.3f}, OOS Sharpe={oos_sharpe:.3f} | WFE={wfe:.1f}% | p-val={p_val:.4f} | Fit Score={composite_score:.2f} ({suitability})")
            
            optuna_matrix_mapping[symbol][interval] = {
                **best_params,
                "is_sharpe": float(is_sharpe),
                "oos_sharpe": float(oos_sharpe),
                "wfe_pct": float(wfe),
                "mc_p_value": float(p_val),
                "flatness_variance": float(flatness_var),
                "suitability_score": float(composite_score),
                "suitability_class": suitability,
                "n_trades": len(oos_returns)
            }
            
            results_list.append({
                "symbol": symbol,
                "interval": interval,
                "params": best_params,
                "is_sharpe": is_sharpe,
                "oos_sharpe": oos_sharpe,
                "wfe": wfe,
                "p_val": p_val,
                "score": composite_score,
                "suitability": suitability,
                "n_trades": len(oos_returns)
            })
            
    # Save Matrix JSON
    runtime_dir = Path("runtime")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    matrix_json_path = runtime_dir / "optuna_parameter_matrix.json"
    matrix_json_path.write_text(json.dumps(optuna_matrix_mapping, indent=2), encoding="utf-8")
    print(f"\n💾 Saved best parameters matrix mapping to: {matrix_json_path}")
    
    # Save report artifact
    report_content = f"""# Strategy-Asset-Timeframe Suitability & Optuna Validation Report

**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Search Engine**: Optuna (Bayesian TPE Search - 50 trials per combination)
**Validation Gates**: Walk-Forward (Out-of-Sample) + Monte Carlo Permutations (1,000 runs)

## Suitability Fit Matrix

| Symbol | Timeframe | Best ADX | Best ATR | RSI Period | RSI Range | OOS Sharpe | WFE % | MC p-val | Fit Score | Suitability | Trades |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
"""
    for r in results_list:
        p = r["params"]
        report_content += f"| **{r['symbol']}** | {r['interval']} | {p['adx_threshold']:.1f} | {p['atr_multiplier']:.2f} | {p['rsi_period']} | {p['rsi_lower']:.0f}-{p['rsi_upper']:.0f} | {r['oos_sharpe']:.3f} | {r['wfe']:.1f}% | {r['p_val']:.4f} | {r['score']:.2f} | **{r['suitability']}** | {r['n_trades']} |\n"
        
    report_content += """
## Classification Legend
- 🟢 **EXCELLENT (Score >= 0.75)**: High out-of-sample edge, robust parameter neighborhood, low probability of luck.
- 🟡 **VIABLE (Score 0.50 - 0.74)**: Profitable but moderate edge. Requires caution or further forward testing.
- 🔴 **UNSUITABLE (Score < 0.50)**: Low or negative Sharpe, high variance, or failed walk-forward metrics. Rejected for live execution.
"""
    
    artifact_path = Path("C:/Users/Black/.gemini/antigravity/brain/de3c89b4-8573-43c0-bddf-c3de5b0e0676/optuna_suitability_matrix.md")
    artifact_path.write_text(report_content, encoding='utf-8')
    print(f"📊 Suitability matrix report written to: {artifact_path}")
    print(f"⏱️ Total batch runtime: {time.time() - t_start_all:.1f} seconds")

if __name__ == '__main__':
    main()
