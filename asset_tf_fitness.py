from __future__ import annotations
from typing import Dict, Tuple

# ─────────────────────────────────────────────────────────────────────
# FITNESS MATRIX
# Key: (signal_family, asset_role, timeframe)
# Value: {
#   "score": float 0.0-1.0   — suitability (< BLOCK_THRESHOLD → hard block)
#   "min_bars": int           — minimum bars before signal can fire
#   "reason": str             — human-readable rationale
# }
# ─────────────────────────────────────────────────────────────────────

BLOCK_THRESHOLD = 0.30   # score < 0.30 = hard block regardless of bars

ASSET_TF_FITNESS: Dict[Tuple[str, str, str], Dict] = {

    # ── ORDER FLOW ──────────────────────────────────────────────────
    # Needs high liquidity + tight spread. anchor=BTC only meaningful on m1.
    ("order_flow", "anchor", "1m"):  {"score": 0.92, "min_bars": 35,  "reason": "BTC m1 order flow has real signal — highest liquidity"},
    ("order_flow", "anchor", "5m"):  {"score": 0.85, "min_bars": 35,  "reason": "BTC m5 order flow — still viable"},
    ("order_flow", "anchor", "15m"): {"score": 0.70, "min_bars": 35,  "reason": "BTC m15 — order flow diffuses, weaker"},
    ("order_flow", "anchor", "1h"):  {"score": 0.45, "min_bars": 35,  "reason": "BTC 1h order flow — too slow for microstructure"},
    ("order_flow", "major",  "1m"):  {"score": 0.55, "min_bars": 35,  "reason": "ETH m1 — noisier than BTC"},
    ("order_flow", "major",  "5m"):  {"score": 0.72, "min_bars": 35,  "reason": "ETH m5 — acceptable"},
    ("order_flow", "major",  "15m"): {"score": 0.60, "min_bars": 35,  "reason": "ETH m15 — marginal"},
    ("order_flow", "alt",    "1m"):  {"score": 0.10, "min_bars": 100, "reason": "BLOCK — SOL m1 too thin, spread dominates signal"},
    ("order_flow", "alt",    "5m"):  {"score": 0.42, "min_bars": 50,  "reason": "SOL m5 — borderline, use with spread filter"},
    ("order_flow", "alt",    "15m"): {"score": 0.55, "min_bars": 50,  "reason": "SOL m15 — acceptable for alts"},

    # ── BREAKOUT ────────────────────────────────────────────────────
    # Needs confirmed compression period before break. m1 breakouts = fakeout heavy.
    ("breakout",   "anchor", "1m"):  {"score": 0.50, "min_bars": 50,  "reason": "BTC m1 breakout — high fakeout rate, needs strong confirmation"},
    ("breakout",   "anchor", "5m"):  {"score": 0.82, "min_bars": 50,  "reason": "BTC m5 breakout — solid, lower fakeout"},
    ("breakout",   "anchor", "15m"): {"score": 0.90, "min_bars": 50,  "reason": "BTC m15 breakout — institutional quality"},
    ("breakout",   "anchor", "1h"):  {"score": 0.88, "min_bars": 50,  "reason": "BTC 1h breakout — high conviction, less frequent"},
    ("breakout",   "major",  "1m"):  {"score": 0.30, "min_bars": 60,  "reason": "ETH m1 — borderline block, fakeout heavy"},
    ("breakout",   "major",  "5m"):  {"score": 0.75, "min_bars": 50,  "reason": "ETH m5 — good"},
    ("breakout",   "major",  "15m"): {"score": 0.85, "min_bars": 50,  "reason": "ETH m15 — preferred"},
    ("breakout",   "alt",    "1m"):  {"score": 0.10, "min_bars": 100, "reason": "BLOCK — SOL m1 breakout = noise"},
    ("breakout",   "alt",    "5m"):  {"score": 0.52, "min_bars": 60,  "reason": "SOL m5 — use only with volume confirmation"},
    ("breakout",   "alt",    "15m"): {"score": 0.75, "min_bars": 60,  "reason": "SOL m15 — preferred for alts"},
    ("breakout",   "alt",    "1h"):  {"score": 0.80, "min_bars": 60,  "reason": "SOL 1h — high quality for alts"},

    # ── MEAN REVERSION ──────────────────────────────────────────────
    # Needs stationary regime. m1 mean reversion = fighting trend noise.
    ("mean_reversion", "anchor", "1m"):  {"score": 0.28, "min_bars": 60, "reason": "BLOCK — BTC m1 MR: 20 bar = 20min context too short"},
    ("mean_reversion", "anchor", "5m"):  {"score": 0.68, "min_bars": 60, "reason": "BTC m5 — 100 min context, acceptable for MR"},
    ("mean_reversion", "anchor", "15m"): {"score": 0.85, "min_bars": 60, "reason": "BTC m15 — ideal for mean reversion"},
    ("mean_reversion", "anchor", "1h"):  {"score": 0.82, "min_bars": 60, "reason": "BTC 1h MR — high quality, slow signals"},
    ("mean_reversion", "major",  "1m"):  {"score": 0.20, "min_bars": 80, "reason": "BLOCK — ETH m1 MR not viable"},
    ("mean_reversion", "major",  "5m"):  {"score": 0.65, "min_bars": 60, "reason": "ETH m5 — marginal but acceptable"},
    ("mean_reversion", "major",  "15m"): {"score": 0.82, "min_bars": 60, "reason": "ETH m15 — preferred"},
    ("mean_reversion", "alt",    "1m"):  {"score": 0.05, "min_bars": 100,"reason": "BLOCK — SOL m1 MR meaningless"},
    ("mean_reversion", "alt",    "5m"):  {"score": 0.40, "min_bars": 80, "reason": "SOL m5 — borderline"},
    ("mean_reversion", "alt",    "15m"): {"score": 0.75, "min_bars": 80, "reason": "SOL m15 — acceptable"},
    ("mean_reversion", "alt",    "1h"):  {"score": 0.82, "min_bars": 80, "reason": "SOL 1h — preferred for alts MR"},

    # ── CONTINUATION (trend following) ──────────────────────────────
    # MACD needs 35+ bars for validity. At m1, 35 bars = 35 minutes — too short.
    ("continuation", "anchor", "1m"):  {"score": 0.40, "min_bars": 50,  "reason": "BTC m1 continuation — MACD noise, use only with m5 bias confirm"},
    ("continuation", "anchor", "5m"):  {"score": 0.75, "min_bars": 50,  "reason": "BTC m5 — solid trend following"},
    ("continuation", "anchor", "15m"): {"score": 0.90, "min_bars": 50,  "reason": "BTC m15 — best for trend continuation"},
    ("continuation", "anchor", "1h"):  {"score": 0.88, "min_bars": 50,  "reason": "BTC 1h — high conviction, infrequent"},
    ("continuation", "major",  "1m"):  {"score": 0.30, "min_bars": 50,  "reason": "ETH m1 — borderline, high noise"},
    ("continuation", "major",  "5m"):  {"score": 0.70, "min_bars": 50,  "reason": "ETH m5 — good"},
    ("continuation", "major",  "15m"): {"score": 0.85, "min_bars": 50,  "reason": "ETH m15 — preferred"},
    ("continuation", "alt",    "1m"):  {"score": 0.10, "min_bars": 100, "reason": "BLOCK — SOL m1 continuation meaningless"},
    ("continuation", "alt",    "5m"):  {"score": 0.48, "min_bars": 60,  "reason": "SOL m5 — borderline"},
    ("continuation", "alt",    "15m"): {"score": 0.78, "min_bars": 60,  "reason": "SOL m15 — preferred"},
    ("continuation", "alt",    "1h"):  {"score": 0.85, "min_bars": 60,  "reason": "SOL 1h — best for alts trend"},

    # ── DIVERGENCE ──────────────────────────────────────────────────
    # Fractal detection needs REAL swing structure. m1 = 100% false signals.
    ("divergence",   "anchor", "1m"):  {"score": 0.05, "min_bars": 100, "reason": "BLOCK — m1 fractals are microstructure noise, not swings"},
    ("divergence",   "anchor", "5m"):  {"score": 0.68, "min_bars": 80,  "reason": "BTC m5 — minimum viable for divergence"},
    ("divergence",   "anchor", "15m"): {"score": 0.85, "min_bars": 80,  "reason": "BTC m15 — preferred, real swing structure"},
    ("divergence",   "anchor", "1h"):  {"score": 0.88, "min_bars": 80,  "reason": "BTC 1h — high quality divergence"},
    ("divergence",   "major",  "1m"):  {"score": 0.05, "min_bars": 100, "reason": "BLOCK — same reason as BTC m1"},
    ("divergence",   "major",  "5m"):  {"score": 0.62, "min_bars": 80,  "reason": "ETH m5 — marginal"},
    ("divergence",   "major",  "15m"): {"score": 0.80, "min_bars": 80,  "reason": "ETH m15 — good"},
    ("divergence",   "alt",    "1m"):  {"score": 0.02, "min_bars": 100, "reason": "BLOCK — absolute block"},
    ("divergence",   "alt",    "5m"):  {"score": 0.40, "min_bars": 100, "reason": "SOL m5 — borderline, use conservatively"},
    ("divergence",   "alt",    "15m"): {"score": 0.72, "min_bars": 100, "reason": "SOL m15 — acceptable"},
    ("divergence",   "alt",    "1h"):  {"score": 0.82, "min_bars": 100, "reason": "SOL 1h — preferred for alts divergence"},

    # ── VOLATILITY EVENT ────────────────────────────────────────────
    # Volume spike + vol expansion. Viable across TFs and assets.
    ("volatility_event", "anchor", "1m"):  {"score": 0.80, "min_bars": 35, "reason": "BTC m1 vol event — fast reaction needed, viable"},
    ("volatility_event", "anchor", "5m"):  {"score": 0.75, "min_bars": 35, "reason": "BTC m5 — slightly slower but confirmed"},
    ("volatility_event", "anchor", "15m"): {"score": 0.70, "min_bars": 35, "reason": "BTC m15 — event already mostly priced"},
    ("volatility_event", "major",  "1m"):  {"score": 0.72, "min_bars": 35, "reason": "ETH m1 — viable"},
    ("volatility_event", "major",  "5m"):  {"score": 0.70, "min_bars": 35, "reason": "ETH m5 — good"},
    ("volatility_event", "alt",    "5m"):  {"score": 0.65, "min_bars": 35, "reason": "SOL m5 — acceptable"},
    ("volatility_event", "alt",    "15m"): {"score": 0.60, "min_bars": 35, "reason": "SOL m15 — lagged but confirmed"},

    # ── CROSS ASSET ─────────────────────────────────────────────────
    # BTC correlation is m1 noise. Meaningful only at m5+.
    ("cross_asset",  "anchor", "1m"):  {"score": 0.20, "min_bars": 50, "reason": "BLOCK — m1 BTC corr = instantaneous noise"},
    ("cross_asset",  "anchor", "5m"):  {"score": 0.72, "min_bars": 50, "reason": "BTC m5 cross-asset — meaningful"},
    ("cross_asset",  "major",  "5m"):  {"score": 0.80, "min_bars": 50, "reason": "ETH m5 vs BTC — best cross-asset signal"},
    ("cross_asset",  "major",  "15m"): {"score": 0.82, "min_bars": 50, "reason": "ETH m15 — high quality"},
    ("cross_asset",  "alt",    "5m"):  {"score": 0.70, "min_bars": 50, "reason": "SOL m5 vs BTC — good"},
    ("cross_asset",  "alt",    "15m"): {"score": 0.78, "min_bars": 50, "reason": "SOL m15 — preferred"},

    # ── FUNDING RATE REVERSION (crypto-native) ──────────────────────
    ("funding_reversion", "anchor", "1m"):  {"score": 0.88, "min_bars": 35, "reason": "BTC funding reversion — high liquidity enables fast execution"},
    ("funding_reversion", "anchor", "5m"):  {"score": 0.88, "min_bars": 35, "reason": "BTC m5 — equivalent quality"},
    ("funding_reversion", "major",  "5m"):  {"score": 0.78, "min_bars": 35, "reason": "ETH m5 funding reversion — viable"},
    ("funding_reversion", "alt",    "15m"): {"score": 0.65, "min_bars": 35, "reason": "SOL m15 — acceptable, thinner market"},

    # ── OI REVERSAL (crypto-native) ─────────────────────────────────
    ("oi_reversal",  "anchor", "5m"):  {"score": 0.82, "min_bars": 35, "reason": "BTC m5 OI divergence — real signal"},
    ("oi_reversal",  "anchor", "15m"): {"score": 0.85, "min_bars": 35, "reason": "BTC m15 — confirmed"},
    ("oi_reversal",  "major",  "5m"):  {"score": 0.72, "min_bars": 35, "reason": "ETH m5 — good"},
    ("oi_reversal",  "major",  "15m"): {"score": 0.78, "min_bars": 35, "reason": "ETH m15 — preferred"},
    ("oi_reversal",  "alt",    "15m"): {"score": 0.62, "min_bars": 35, "reason": "SOL m15 — marginal"},
}


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def get_fitness(signal_family: str, asset_role: str, interval: str) -> Dict:
    """
    Returns fitness dict for (signal_family, asset_role, interval).
    Falls back to penalized defaults for unregistered combinations.
    """
    key = (signal_family, asset_role, interval)
    if key in ASSET_TF_FITNESS:
        return ASSET_TF_FITNESS[key]
    # Unknown combination — conservative fallback
    return {
        "score": 0.20,
        "min_bars": 100,
        "reason": f"Unregistered combination ({signal_family}, {asset_role}, {interval}) — blocked by default",
    }


def is_fitness_ok(
    signal_family: str,
    asset_role: str,
    interval: str,
    n_bars: int,
) -> bool:
    """
    Returns True only if:
    1. fitness score >= BLOCK_THRESHOLD (0.30)
    2. n_bars >= required min_bars

    This is the single gate used by _compute_strategies().
    """
    fit = get_fitness(signal_family, asset_role, interval)
    if fit["score"] < BLOCK_THRESHOLD:
        return False
    if n_bars < fit["min_bars"]:
        return False
    return True


def fitness_summary(signal_family: str, asset_role: str, interval: str, n_bars: int) -> Dict:
    """Returns full fitness assessment dict for logging/debugging."""
    fit = get_fitness(signal_family, asset_role, interval)
    ok = is_fitness_ok(signal_family, asset_role, interval, n_bars)
    return {
        "signal_family": signal_family,
        "asset_role": asset_role,
        "interval": interval,
        "n_bars": n_bars,
        "score": fit["score"],
        "min_bars": fit["min_bars"],
        "reason": fit.get("reason", ""),
        "passed": ok,
        "block_reason": (
            "hard_block_score" if fit["score"] < BLOCK_THRESHOLD
            else "insufficient_bars" if n_bars < fit["min_bars"]
            else None
        ),
    }
