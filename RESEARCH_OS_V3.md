# Research OS V3

Research OS V3 is an executable realtime research system wired for Hyperliquid market data.

## Locked operating principle

Input is limited to market data and metadata that the system is actually given.
Output of the synthesis layer is strategy candidates, not automatic GO decisions.
GO can only emerge after validation, review, and explicit decision gates.

## Pipeline

OHLCV -> Factors -> Indicators -> Signals -> Strategy -> Validation -> Decision

Each upstream layer shapes and disciplines the next layer.

## V3 modules

- `hyperliquid_ws_client.py`: websocket adapter with reconnect loop and subscription management.
- `realtime_engine.py`: incremental OHLCV, factor, indicator, signal, and strategy state engine.
- `app.py`: FastAPI app exposing snapshot and health endpoints plus a browser dashboard.
- `static/index.html`: realtime control room UI.
- `config.example.json`: sample config for symbols, intervals, thresholds, and runtime mode.

## Realtime flow

1. Connect to Hyperliquid websocket.
2. Subscribe to trades, candle, bbo, and allMids channels.
3. Normalize events into a unified internal schema.
4. Update rolling market state.
5. Compute factors incrementally from realtime bars and quotes.
6. Compute indicators from those factors and bars.
7. Evaluate signal templates from the current indicator state.
8. Build strategy candidates from valid signal states.
9. Expose state through API and the dashboard.

## Hyperliquid notes

Hyperliquid docs expose websocket endpoints at:
- mainnet: `wss://api.hyperliquid.xyz/ws`
- testnet: `wss://api.hyperliquid-testnet.xyz/ws`

The docs also note that automated clients must handle disconnects and reconnect gracefully.

## Scope of this V3 code

This implementation focuses on realtime ingest, factor and indicator state, signal evaluation, and strategy candidate generation.
It does not place live orders.
