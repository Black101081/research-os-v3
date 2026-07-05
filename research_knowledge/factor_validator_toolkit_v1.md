# Factor Validator Toolkit v1

Purpose: validate factor objects for interpretability, non-duplication, and downstream usefulness.

## Validation modules

### 1. Measurement completeness
- factor_id, family, tier, title, novelty_claim exist
- thesis_type, core_question, intuition exist
- failure_modes and validation_targets exist

### 2. Interpretive discipline
- information_edge present
- non_edge_warning present
- misuse_patterns present
- edge/frontier factors identify a baseline_control

### 3. Regime realism
- preferred_regimes and avoid_regimes declared
- failure modes align with regime limits

### 4. Downstream mapping
- signal_roles declared
- strategy_roles declared
- validator_checks align with intended usage

## Decisions
- PASS
- PASS_WITH_WARNINGS
- REVISE
- REJECT
