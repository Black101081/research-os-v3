# Expanded Indicator Architecture v2

Purpose: define a research-grade indicator taxonomy that sits above the factor layer, preserves lineage, and expands breadth without collapsing into repetitive classics.

## Design objectives
- Build an indicator layer that is broader than common retail defaults.
- Keep indicators interpretable and traceable to factor or bar dependencies.
- Force each indicator to declare novelty, overlap risk, and downstream signal utility.
- Keep validator compatibility from day one.

## Five indicator families

### 1. Displacement and equilibrium indicators
Interpret how far price sits from local balance, distribution center, or equilibrium drift.

### 2. Trend and path indicators
Interpret alignment, continuation quality, decay, and directional coherence.

### 3. Volatility and compression indicators
Interpret expansion, squeeze quality, shock absorption, and instability.

### 4. Participation and conviction indicators
Interpret whether activity confirms, weakens, or contradicts price motion.

### 5. Microstructure and execution indicators
Interpret tradeability, tape quality, liquidity stress, and local quote pressure.

## Three research tiers
- Core tier: interpretable and likely portable.
- Edge tier: differentiated and still broadly testable.
- Frontier tier: composite or less common structures that may provide research edge.

## Anti-duplication rules
- Changing only a smoothing period is not enough to justify a new indicator.
- Indicators that merely restate a factor must explain why the indicator form matters.
- Composite indicators must identify which parent signals they improve versus duplicate.
- Every indicator must state its nearest neighbors and how it differs.

## Required fields for every indicator candidate
- indicator_id
- family
- tier
- title
- intuition
- inputs
- nearest_neighbors
- novelty_claim
- overlap_risk
- failure_modes
- downstream_uses
- validator_checks

## Expansion standard
Each family should contain:
- 3 core indicators
- 3 edge indicators
- 4 frontier indicators
Total per family: 10
Total across five families: 50
