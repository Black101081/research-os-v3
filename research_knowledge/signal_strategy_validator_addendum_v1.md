# Signal and Strategy Validator Addendum v1

## Signal thesis checks
- thesis exists and is specific rather than generic
- template_family exists and matches registry family taxonomy
- preferred_regimes and avoid_regimes are both present
- required_factors and required_indicators are explicitly declared
- trigger_logic and invalidation_logic are both described
- execution note exists
- thesis names at least one failure or contamination risk

## Strategy thesis checks
- strategy schema fields are complete for strategy_spec_v1
- strategy family maps to a validation focus in strategy_registry
- lifecycle stage order is present and internally consistent
- strategy thesis explains why signal becomes tradeable rather than only detectable
- risk logic and execution assumptions are explicit
- research lifecycle includes at least one rejection or revision path

## Decision rubric
- PASS: structurally complete, regime-fit clear, validation linkage present
- PASS_WITH_WARNINGS: complete but still generic, thin novelty, or incomplete failure articulation
- REVISE: unclear thesis, weak linkage, or missing critical fields
- REJECT: broken schema or incoherent mapping
