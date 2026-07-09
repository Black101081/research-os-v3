---
name: scientific-research-methodology
description: Guidelines and best practices for conducting empirical, scientific, and quantitative research on trading strategies, including hypothesis testing and cross-validation.
---
# Scientific Research Methodology for Quantitative Trading

This skill defines the standard operating procedures (SOP) for conducting scientific research on financial time series and quantitative trading strategies.

## 1. Hypothesis Formulation
- State a clear, falsifiable null hypothesis ($H_0$) and alternative hypothesis ($H_1$).
- Example: 
  - $H_0$: The dynamic order book imbalance factor (D-OBI) has no predictive power over 5-minute price direction.
  - $H_1$: The dynamic order book imbalance factor (D-OBI) has positive predictive power over 5-minute price direction.

## 2. Quantitative Testing & Cross-Validation
- **Purged k-Fold Cross-Validation**: Used to prevent data leakage from overlapping labels in time-series data.
- **Walk-Forward Analysis (WFA)**:
  - In-Sample (IS) for parameter optimization.
  - Out-of-Sample (OOS) to measure generalization.
  - Walk-Forward Efficiency (WFE) should exceed $60\%$.

## 3. Statistical Significance
- Use Welch's t-test or Mann-Whitney U test to compare strategy returns vs benchmark.
- Set significance level $\alpha = 0.05$.
- Compute p-value to reject $H_0$.
