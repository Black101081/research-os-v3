# Indicator Validator Toolkit v1

Purpose: validate indicator theses and templates as research objects, not only as schema entries.

## Validation modules

### 1. Thesis completeness
Checks:
- core_question present
- information_edge present
- non_edge_warning present
- failure_archetypes present
- misuse_patterns present
- validation_targets present

### 2. Dependency clarity
Checks:
- nearest_factors declared
- nearest_indicators declared
- transform_logic explains why indicator form matters beyond factor inputs
- composite indicators declare whether they improve timing, filtering, or execution realism

### 3. Interpretive uniqueness
Checks:
- indicator does not merely rename parent factor logic
- novelty claim is distinguishable from nearest neighbors
- control indicators are labeled as controls rather than differentiated alpha
- edge/frontier indicators specify which baseline control they aim to beat

### 4. Regime realism
Checks:
- preferred_regimes stated
- avoid_regimes stated
- misuse patterns match regime limitations
- failure archetypes reflect realistic contamination states

### 5. Signal and strategy utility
Checks:
- signal_roles explicitly stated
- strategy_roles explicitly stated
- validation_targets are testable in downstream playbooks
- indicator can be rejected if it adds no measurable improvement

## Indicator-specific decisions
- PASS: complete, differentiated, realistic, and testable
- PASS_WITH_WARNINGS: useful but too generic, too overlapping, or under-specified
- REVISE: weak thesis, weak transform rationale, or shallow validation targets
- REJECT: decorative, redundant, or logically incoherent
