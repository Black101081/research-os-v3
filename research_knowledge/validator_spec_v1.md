# Research Validator Spec v1

Purpose: ensure the research repositories are not only large, but internally consistent, differentiated, falsifiable, and connected to runtime usage.

## Validation layers

### 1. Structural validation
Checks:
- required fields exist
- family names are valid
- tiers are one of core, edge, frontier
- ids are unique
- registry references resolve to existing documents
- no empty novelty or failure mode fields

### 2. Redundancy validation
Checks:
- candidate is not a trivial lookback clone of an existing factor
- novelty claim differs from nearest neighbors
- same underlying quantity is not duplicated across factor and indicator layers without explanation
- pairwise similarity score stays below threshold unless explicitly whitelisted

### 3. Thesis-fit validation
Checks:
- every factor states at least one plausible downstream use
- every indicator maps to at least one factor or bar dependency
- every signal references meaningful factor or indicator parents
- every strategy family references relevant validation focus

### 4. Regime-fit validation
Checks:
- preferred and avoid regimes are stated
- directional templates do not claim universal regime compatibility
- mean reversion templates explicitly state trend contamination risk
- breakout templates explicitly state false-break risk and participation requirements

### 5. Research-quality validation
Checks:
- interpretability score
- novelty score
- falsifiability score
- portability score
- execution relevance score
- expected failure clarity score

## Suggested scoring rubric
- 0 to 5 for each research-quality dimension
- 24+ total: strong candidate
- 18 to 23: usable but needs review
- below 18: archive or revise

## Validator outputs
- PASS
- PASS_WITH_WARNINGS
- REVISE
- REJECT

## Runtime integration plan
- Add offline validator script for repository files.
- Add API endpoint for validator summaries.
- Surface validator output in UI lifecycle board and repository views.
- Block strategy promotion when upstream research objects are unresolved.
