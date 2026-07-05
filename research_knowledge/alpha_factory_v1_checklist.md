# Alpha Factory v1 Checklist

## Goal
Close the v1 scope as a usable end-to-end research demo rather than an open-ended architecture exercise.

## Completed
- Signal candidate generation and pruning.
- Validation runner with scorecards and regime panels.
- Alpha lifecycle and promotion/demotion decisions.
- Registry/store persistence for definitions, scorecards, lifecycle events, and decay profiles.
- Ranking integration, diversification filter, and revalidation scheduler.
- Real validation bridge using backtest runner demo and BTC 15m live soak context.
- Research brief generator.
- One-command Alpha Factory demo runner.

## Hardening
- Registry has explicit revalidation task storage.
- Runner exposes healthcheck summary.
- Demo runner supports CLI arguments for output directory and candidate count.
