from __future__ import annotations

from pathlib import Path
import json
import logging
from realtime_engine import ResearchEngine
from async_registry_writer import AsyncRegistryWriter
from telemetry import TelemetryTracker
from paper_broker import PaperBroker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'config.example.json').read_text())

engine = ResearchEngine(
    symbols=CONFIG['symbols'],
    max_bars=CONFIG['runtime']['max_bars'],
    thresholds=CONFIG['thresholds']
)
registry = AsyncRegistryWriter(BASE / 'runtime')
telemetry = TelemetryTracker()
broker = PaperBroker(initial_balance=10000.0)

kill_switch_active = False
trading_mode = 'paper'
