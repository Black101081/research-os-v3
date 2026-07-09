---
name: mathematical-modeling-and-optimization
description: Guidelines and procedures for formulating mathematical models, implementing numerical optimization (Optuna, scipy.optimize), and analyzing parameter sensitivity.
---
# Mathematical Modeling and Optimization

This skill provides instruction on building robust mathematical models and using numerical methods to optimize strategy parameters.

## 1. Objective Function Formulation
- Define the optimization metric clearly (e.g., Sharpe Ratio, Sortino Ratio, Calmar Ratio, or Custom Multi-objective Fitness).
- Always include penalties for transaction costs, slippage, and high volatility.

## 2. Sensitivity and Robustness Analysis
- Avoid point-in-time optimization. Instead, optimize over a neighborhood of parameters (Flatness Check).
- Flatness variance calculation:
  $$\sigma^2_{\text{neighbors}} = \frac{1}{N}\sum_{i=1}^N (x_i - \mu_{\text{best}})^2$$
  If the variance is high, the parameter set is in a "sharp peak" and likely to fail in live trading.

## 3. Advanced Numerical Tools
- Use **Optuna** for Bayesian optimization (TPE sampler).
- Apply constraints using penalty functions to prevent unreasonable parameter bounds.
