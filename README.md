---
title: Research OS V3
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Research OS V3

Executable realtime research system for Hyperliquid websocket market data.

## Added in this revision
- **Phase 2: Dynamic Signal Pipeline**: Connected Alpha Factory and Live Engine via `promoted_signal_bridge.py` to evaluate dynamic candidates.
- **Safe Expression Evaluation**: Safe evaluation of indicator-based logical conditions using a restricted sandbox `safe_eval_expression`.
- **Dynamic Expression Generation**: Built candidates dynamically based on factor catalog requirements in `signal_generator.py`.
- **6 Business Logic Hardening Fixes**:
  - Restrict tradable regimes to `uptrend`, `downtrend`, `range_chop` (high volatility disabled).
  - Bollinger squeeze breakout logic uses previous-bar width state tracking to avoid immediate expansion block.
  - Centralized single-source-of-truth thresholds in `indicator_keys.py`.
  - Dynamic entry-side (`long`/`short`) inference for Z-Score and MACD signals.
  - Volatility-based dynamic take-profit fallback.
  - SciPy `lfilter` normalized EMA computation.
- **UI/UX Polish**: Glassmorphism premium dark cards, neon glow hover micro-animations, and scroll-wrapped boards for responsive layout.

## What it does
- Connects directly to Hyperliquid websocket.
- Subscribes to trades, candle, bbo, and allMids.
- Computes rolling OHLCV state.
- Computes incremental factors and indicators.
- Computes regime state.
- Evaluates signal states from toolkit-aligned logic.
- Builds strategy candidates.
- Auto-builds `strategy_spec_v1` for active and execution-ready signals.
- Auto-builds playbook lifecycle packets for those specs.
- Writes runtime registry artifacts.
- Exposes validation and spec previews through FastAPI and the browser dashboard.

## Warmup
- `bootstrap_ohlcv.py` pulls historical candles from the Hyperliquid Info endpoint `candleSnapshot` before websocket streaming starts.
- This gives the engine enough OHLCV history to compute rolling factors and indicators immediately.

## Testing
- `python run_full_test_suite.py` runs the full unit and API suite and writes reports to `runtime/test_report.json` and `runtime/test_report.md`.
- Coverage targets engine parsing, signal-to-spec flow, warmup bootstrap, registry persistence, and API surfaces.

## Replay and lifecycle
- `/api/replay-demo` runs a deterministic paper replay path that forces a signal-active case and proves `signals -> strategy_spec_v1 -> playbook packet`.
- The UI now includes a lifecycle board and replay tab for visual inspection.

## Research knowledge repositories
- `research_knowledge/factor_library.md` and `factor_registry.json` define atomic factor families and their downstream usage.
- `research_knowledge/indicator_library.md` and `indicator_registry.json` define interpretation-layer indicators and dependencies.
- `research_knowledge/signal_thesis_templates.md` and `signal_registry.json` define supported signal theses and machine-readable templates.
- `research_knowledge/strategy_thesis_templates.md` and `strategy_registry.json` define the strategy conversion layer and lifecycle mapping.
- `research_knowledge/knowledge_map.md` explains the relationship between the four repositories and the runtime code.

- `research_knowledge/factor_architecture_v2.md` defines the five-family, 100-factor expansion standard.
- `research_knowledge/expanded_factor_catalog_v1.json` provides the first high-breadth factor catalog with 5 families x 20 candidates.
- `research_knowledge/validator_spec_v1.md` and `validator_registry.json` define the validation framework for research quality and anti-duplication.

- `research_knowledge/indicator_architecture_v2.md` defines the five-family indicator taxonomy.
- `research_knowledge/expanded_indicator_catalog_v1.json` provides 5 families x 10 differentiated indicator candidates.
- `validator_runner.py` executes the repository validator and writes `runtime/research_validator_report.json`.

- `research_knowledge/signal_architecture_v2.md` defines the 20-signal expansion standard across five families.
- `research_knowledge/expanded_signal_catalog_v1.json` provides 20 expanded signal templates derived from the factor and indicator catalogs.
- `research_knowledge/expanded_strategy_catalog_v1.json` provides 8 strategy families mapped from the expanded signal layer.

- `research_knowledge/novelty_refinement_plan_v1.md` prioritizes which common templates should be upgraded first.
- `backtest_bridge.py` builds backtest jobs from the expanded strategy catalog and applies a simple decision gate demo.

- `research_knowledge/backtest_runner_contract_v1.md` defines the backtest handoff contract.
- `baseline_backtest_runner.py` simulates baseline runner outputs and decision gates for the expanded strategy families.
