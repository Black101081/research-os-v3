import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realtime_engine import ResearchEngine

engine = ResearchEngine(symbols=['BTC'], max_bars=500, thresholds={})
for i in range(40):
    px = 60000 + i
    engine.process_message({'channel': 'candle', 'data': {'coin': 'BTC', 't': 1700000000000 + i*60000, 'o': px-1, 'h': px+2, 'l': px-2, 'c': px, 'v': 10+i}})
engine.process_message({'channel': 'bbo', 'data': {'coin': 'BTC', 'bid': 60039.5, 'ask': 60040.5}})
engine.process_message({'channel': 'trades', 'data': [{'coin': 'BTC', 'px': 60045.0, 'sz': 0.25, 'side': 'B', 'time': 1700002405000}]})
snap = engine.snapshot()['BTC']
print(json.dumps(snap))
