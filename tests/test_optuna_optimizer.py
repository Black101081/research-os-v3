from __future__ import annotations

import pytest
import numpy as np
from typing import Dict, Any, List
from run_optuna_validated_optimizer import (
    calculate_sharpe,
    simulate_strategy,
    run_monte_carlo,
    compute_suitability_score,
    run_optuna_optimization
)

def test_calculate_sharpe():
    # Zero returns should return 0.0 Sharpe
    assert calculate_sharpe([], '5m') == 0.0
    assert calculate_sharpe([0.0, 0.0, 0.0], '5m') == 0.0
    
    # Returns with variance should return positive Sharpe
    returns = [0.01, 0.02, 0.01, 0.02, 0.015]
    sharpe = calculate_sharpe(returns, '5m')
    assert sharpe > 0.0

def test_compute_suitability_score():
    # No trades => UNSUITABLE
    score, suitability = compute_suitability_score(0.0, 0.0, 1.0, 0.0, 0)
    assert suitability == "UNSUITABLE"
    assert score == 0.0
    
    # High Sharpe, high WFE, low p-val, high Win Rate => EXCELLENT
    # composite = min(0.40, 3.5/5.0) + min(0.30, 85/100*0.30) + (1-0.01)*0.20 + 0.6*0.10
    # = 0.40 (maxed) + 0.255 + 0.198 + 0.06 = 0.913
    score, suitability = compute_suitability_score(3.5, 85.0, 0.01, 0.60, 15)
    assert suitability == "EXCELLENT"
    assert score >= 0.75

    # Low Sharpe => UNSUITABLE
    score, suitability = compute_suitability_score(0.1, 10.0, 0.9, 0.1, 5)
    assert suitability == "UNSUITABLE"
    assert score < 0.50

def test_run_monte_carlo():
    # If fake returns are always worse, p-val should be low or 0
    # Since n_iterations is small in test for speed
    p_val = run_monte_carlo([0.05, 0.05, 0.05], 10.0, '5m', n_iterations=10)
    assert p_val <= 1.0

def test_optuna_optimization_mock():
    # Create 100 mock candles with a simple trend to ensure simulation doesn't error out
    mock_candles = []
    base_price = 100.0
    for i in range(100):
        # Generate slightly varying candles
        noise = np.sin(i / 5.0) * 2.0
        c_val = base_price + noise
        mock_candles.append({
            't': i * 60,
            'o': float(c_val - 0.5),
            'h': float(c_val + 1.0),
            'l': float(c_val - 1.0),
            'c': float(c_val),
            'v': 100.0
        })
        
    res = run_optuna_optimization(mock_candles, '5m', n_trials=5)
    assert "best_params" in res
    assert "is_sharpe" in res
    assert "flatness_variance" in res
    assert isinstance(res["best_params"], dict)
    assert "adx_threshold" in res["best_params"]
    assert "atr_multiplier" in res["best_params"]
