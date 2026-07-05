# Factor Template Canon v1

Purpose: standardize how factors are described so every factor can be compared, validated, and mapped downstream.

## Required fields
- factor_id
- canonical_title
- family
- tier
- thesis_type
- core_question
- intuition
- information_edge
- non_edge_warning
- preferred_regimes
- avoid_regimes
- signal_roles
- strategy_roles
- misuse_patterns
- failure_modes
- validation_targets
- baseline_control
- promotion_preference
- validator_checks

## Canon rules
- Every factor must say what it measures before any indicator interpretation is applied.
- Every factor must say where it is likely to fail.
- Edge and frontier factors must state which baseline control they attempt to improve.
- Factors may be useful without being unique alpha; that must be stated explicitly.
