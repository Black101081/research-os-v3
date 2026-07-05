# Strategy Validator Toolkit v1

Purpose: validate strategy theses and templates with stronger emphasis on baseline-beating logic, execution realism, and lifecycle testability.

## Validation modules

### 1. Thesis strength
Checks:
- differentiated_claim present
- baseline_controls present
- why_now_logic present
- failure_archetypes present
- rejection requirements exist

### 2. Testability and falsifiability
Checks:
- validation_targets are measurable
- promotion rule requires beating a named baseline
- rejection rule is explicit
- negative_knowledge_targets exist

### 3. Execution realism
Checks:
- execution_realism_assumptions present
- risk_focus reflects actual fill/slippage/liquidity concerns when relevant
- strategy is not direction-only when execution is central to the thesis

### 4. Lifecycle fitness
Checks:
- lifecycle_requirements declared
- promotion logic aligns with research playbook stages
- strategy can be revised or rejected without ambiguous language

### 5. Portfolio usefulness
Checks:
- portfolio_role is declared or inferable
- strategy adds something different from parent signal alone
- opportunity cost versus filter value is considered when overlay style strategy is used

## Strategy-specific decisions
- PASS: differentiated, falsifiable, execution-aware, and lifecycle-ready
- PASS_WITH_WARNINGS: promising but still generic or thin on realism/rejection logic
- REVISE: weak baseline logic, weak rejection criteria, or vague validation targets
- REJECT: decorative, non-falsifiable, or not credibly tradeable
