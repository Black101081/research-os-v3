import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import websockets

logger = logging.getLogger(__name__)

MAINNET_WS = "wss://api.hyperliquid.xyz/ws"
TESTNET_WS = "wss://api.hyperliquid-testnet.xyz/ws"


class HyperliquidWSClient:
    def __init__(self, url: str, subscriptions: Any, on_message: Callable[[Dict[str, Any]], Any], reconnect_seconds: int = 5):
        self.url = url
        if isinstance(subscriptions, dict):
            self.subscriptions = self._build_subscriptions(subscriptions)
        else:
            self.subscriptions = subscriptions
        self.on_message = on_message
        self.reconnect_seconds = reconnect_seconds
        self._running = False
        self._ws = None

    def _build_subscriptions(self, config: dict) -> list:
        subs = []
        asset_config = config.get("asset_config", {})

        # Legacy fallback — single candle_interval
        if not asset_config:
            for symbol in config.get("symbols", []):
                interval = config.get("candle_interval", "1m")
                subs.append({"type": "candle", "coin": symbol, "interval": interval})
                subs.append({"type": "trades", "coin": symbol})
                subs.append({"type": "bbo",    "coin": symbol})
            subs.append({"type": "allMids"})
            return subs

        # Multi-TF subscription
        for symbol, cfg in asset_config.items():
            for interval in cfg.get("candle_intervals", ["1m"]):
                subs.append({"type": "candle", "coin": symbol, "interval": interval})
            subs.append({"type": "trades", "coin": symbol})
            subs.append({"type": "bbo",    "coin": symbol})
            if cfg.get("subscribe_l2book", False):
                subs.append({"type": "l2Book",         "coin": symbol})
            if cfg.get("subscribe_active_asset_ctx", False):
                subs.append({"type": "activeAssetCtx", "coin": symbol})

        subs.append({"type": "allMids"})
        return subs

    async def _send_subscriptions(self):
        for sub in self.subscriptions:
            payload = {"method": "subscribe", "subscription": sub}
            await self._ws.send(json.dumps(payload))
            logger.info("Subscribed: %s", payload)

    async def run_forever(self):
        self._running = True
        while self._running:
            try:
                logger.info("Connecting to %s", self.url)
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws = ws
                    await self._send_subscriptions()
                    async for raw in ws:
                        try:
                            message = json.loads(raw)
                        except json.JSONDecodeError:
                            logger.warning("Dropped non-json message: %s", raw)
                            continue
                        await self.on_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Websocket loop error: %s", exc)
                await asyncio.sleep(self.reconnect_seconds)

    def stop(self):
        self._running = False

    async def close(self):
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
