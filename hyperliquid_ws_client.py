import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import websockets

logger = logging.getLogger(__name__)

MAINNET_WS = "wss://api.hyperliquid.xyz/ws"
TESTNET_WS = "wss://api.hyperliquid-testnet.xyz/ws"


class HyperliquidWSClient:
    def __init__(self, url: str, subscriptions: List[Dict[str, Any]], on_message: Callable[[Dict[str, Any]], Any], reconnect_seconds: int = 5):
        self.url = url
        self.subscriptions = subscriptions
        self.on_message = on_message
        self.reconnect_seconds = reconnect_seconds
        self._running = False
        self._ws = None

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
