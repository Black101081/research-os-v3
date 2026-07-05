# Indicator Template Canon v1

Purpose: standardize how every indicator is described so the repository remains interpretable, comparable, and validator-friendly.

## Required template fields
- indicator_id
- canonical_title
- family
- tier
- thesis_type
- core_question
- intuition
- information_edge
- non_edge_warning
- inputs
- transform_logic
- preferred_regimes
- avoid_regimes
- nearest_factors
- nearest_indicators
- signal_roles
- strategy_roles
- failure_archetypes
- misuse_patterns
- validation_targets
- baseline_control
- promotion_preference
- validator_checks

## Canon rules
- Every indicator must say what information it adds beyond its nearest factor parents.
- Every indicator must say when it should not be trusted.
- Every edge/frontier indicator must identify which baseline control it is supposed to outperform.
- Composite indicators must identify whether they add timing quality, filter quality, or execution realism.
- Indicators may support signals indirectly; that relationship must still be declared.

## Template grading hints
- Control template: interpretable, portable, common, useful as benchmark.
- Differentiated template: adds context-specific edge over a control template.
- Promotion candidate: differentiated template with clear validation targets and failure clarity.
