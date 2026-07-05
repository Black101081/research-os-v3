# Knowledge Map

## Dependency chain
1. Factor library defines atomic measurements.
2. Indicator library defines interpreted state built from factors or bars.
3. Signal library defines tradable hypotheses using factor and indicator combinations.
4. Strategy library defines how an active signal becomes a research-grade strategy spec.
5. Playbook and validation layers govern decision and promotion.

## Current implementation linkage
- Factor and indicator calculation: `realtime_engine.py`
- Regime classification: `regime_engine.py`
- Signal activation logic: `signal_orchestrator.py`
- Strategy spec construction: `strategy_spec_builder.py`
- Lifecycle packet construction: `playbook_bridge.py`
- Replay path: `paper_replay.py`
