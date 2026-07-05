from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import json
import urllib.request

INFO_URL = 'https://api.hyperliquid.xyz/info'

INTERVAL_MS = {
    '1m': 60_000,
    '3m': 180_000,
    '5m': 300_000,
    '15m': 900_000,
    '30m': 1_800_000,
    '1h': 3_600_000,
    '2h': 7_200_000,
    '4h': 14_400_000,
    '8h': 28_800_000,
    '12h': 43_200_000,
    '1d': 86_400_000,
}


def fetch_candle_snapshot(coin: str, interval: str, lookback_bars: int = 240) -> List[Dict[str, Any]]:
    step = INTERVAL_MS.get(interval, 60_000)
    end_time = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    start_time = end_time - lookback_bars * step
    payload = {
        'type': 'candleSnapshot',
        'req': {
            'coin': coin,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time,
        }
    }
    req = urllib.request.Request(
        INFO_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    return data if isinstance(data, list) else []


def warmup_engine(engine, symbols: List[str], interval: str, lookback_bars: int = 240) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for symbol in symbols:
        candles = fetch_candle_snapshot(symbol, interval, lookback_bars)
        inserted = 0
        for candle in candles:
            engine.process_message({'channel': 'candle', 'data': candle})
            inserted += 1
        counts[symbol] = inserted
    return counts
