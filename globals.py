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
config_path = BASE / 'config.json'
if not config_path.exists():
    config_path = BASE / 'config.example.json'
CONFIG = json.loads(config_path.read_text())

engine = ResearchEngine(
    symbols=CONFIG['symbols'],
    max_bars=CONFIG['runtime']['max_bars'],
    thresholds=CONFIG['thresholds']
)
registry = AsyncRegistryWriter(BASE / 'runtime')
telemetry = TelemetryTracker()
broker = PaperBroker(initial_balance=10000.0)

import sys
from types import ModuleType
import database as _db

class GlobalsModule(ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self._kill_switch_active = False
        self._trading_mode = 'paper'

        # Restore from DB on boot
        try:
            _ks = _db.load_latest_system_event("kill_switch")
            if _ks is not None:
                self._kill_switch_active = (_ks == "true")

            _tm = _db.load_latest_system_event("trading_mode")
            if _tm is not None:
                self._trading_mode = _tm
        except Exception:
            pass  # DB not ready yet on first boot — use defaults

    @property
    def kill_switch_active(self):
        return self._kill_switch_active

    @kill_switch_active.setter
    def kill_switch_active(self, val):
        if self._kill_switch_active != val:
            self._kill_switch_active = val
            try:
                _db.save_system_event("kill_switch", str(val).lower(), triggered_by="api")
            except Exception:
                pass

    @property
    def trading_mode(self):
        return self._trading_mode

    @trading_mode.setter
    def trading_mode(self, val):
        if self._trading_mode != val:
            self._trading_mode = val
            try:
                _db.save_system_event("trading_mode", val, triggered_by="api")
            except Exception:
                pass

# Replace this module in sys.modules
current_module = sys.modules[__name__]
globals_module = GlobalsModule(__name__)

# Copy all attributes
for k, v in list(current_module.__dict__.items()):
    if not k.startswith('__'):
        setattr(globals_module, k, v)

sys.modules[__name__] = globals_module
