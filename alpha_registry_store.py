from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class AlphaRegistryStore:
    def __init__(self, base: str | Path):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.files = {
            'alpha_definitions': self.base / 'alpha_definitions.jsonl',
            'validation_scorecards': self.base / 'validation_scorecards.jsonl',
            'regime_panels': self.base / 'regime_panels.jsonl',
            'decay_profiles': self.base / 'decay_profiles.jsonl',
            'lifecycle_events': self.base / 'lifecycle_events.jsonl',
        }

    def append(self, table: str, payload: Dict[str, Any]) -> None:
        path = self.files[table]
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False) + '\n')
