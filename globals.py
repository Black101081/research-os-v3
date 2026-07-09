from __future__ import annotations

from pathlib import Path
import json
import os
import logging
from realtime_engine import ResearchEngine
from async_registry_writer import AsyncRegistryWriter
from telemetry import TelemetryTracker
from paper_broker import PaperBroker

# Determine Environment (Docker DEV vs HF Space PROD)
APP_ENV = os.getenv("APP_ENV", "production")
if "SPACE_ID" in os.environ:
    APP_ENV = "production"

if APP_ENV == "development":
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
config_path = BASE / 'config.json'
if not config_path.exists():
    config_path = BASE / 'config.example.json'
CONFIG = json.loads(config_path.read_text())

# Synthesize legacy fields for backward compatibility
if 'asset_config' in CONFIG:
    # Auto-configure missing symbols in asset_config
    asset_config = CONFIG['asset_config']
    modified_config = False
    for s in CONFIG.get('symbols', []):
        if s not in asset_config:
            asset_config[s] = {
                "candle_intervals": ["1m", "5m", "15m", "1h"],
                "subscribe_l2book": True,
                "subscribe_active_asset_ctx": True,
                "role": "alt",
                "min_spread_bps": 2.0,
                "max_spread_bps": 15.0,
                "notes": "Auto-configured on boot."
            }
            modified_config = True
    if modified_config:
        try:
            config_path.write_text(json.dumps(CONFIG, indent=2), encoding='utf-8')
        except Exception:
            pass
            
    if 'symbols' not in CONFIG:
        CONFIG['symbols'] = list(CONFIG['asset_config'].keys())
    if 'candle_interval' not in CONFIG:
        first_asset = list(CONFIG['asset_config'].values())[0]
        CONFIG['candle_interval'] = first_asset.get('candle_intervals', ['1m'])[0]
    if 'runtime' in CONFIG:
        if 'max_bars' not in CONFIG['runtime']:
            max_bars_per_tf = CONFIG['runtime'].get('max_bars_per_tf', {})
            CONFIG['runtime']['max_bars'] = max_bars_per_tf.get('1m', 500)

engine = ResearchEngine(
    symbols=CONFIG['symbols'],
    max_bars=CONFIG['runtime']['max_bars'],
    thresholds=CONFIG['thresholds']
)
registry = AsyncRegistryWriter(BASE / 'runtime')
telemetry = TelemetryTracker()
broker = PaperBroker(initial_balance=10000.0)
engine._paper_broker = broker

import sys
from types import ModuleType
import database as _db

class GlobalsModule(ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self._kill_switch_active = False
        self._trading_mode = 'paper'
        orig = sys.modules.get(name)
        self.quality_gate = getattr(orig, "quality_gate", None) if orig else None

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

# Quality Gate — được set bởi SignalOrchestrator khi khởi tạo
if not hasattr(sys.modules[__name__], 'quality_gate'):
    quality_gate = None  # type: ignore

# Replace this module in sys.modules
current_module = sys.modules[__name__]
globals_module = GlobalsModule(__name__)

# Copy all attributes
for k, v in list(current_module.__dict__.items()):
    if not k.startswith('__'):
        setattr(globals_module, k, v)

sys.modules[__name__] = globals_module
