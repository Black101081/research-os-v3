from __future__ import annotations

from pathlib import Path
from datetime import datetime, UTC
import json
from typing import Dict, Any, List


class RegistryWriter:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.root / 'registry_runs.jsonl'
        self.latest_file = self.root / 'latest_snapshot.json'
        self.specs_file = self.root / 'strategy_specs.jsonl'
        self.playbook_file = self.root / 'playbook_packets.jsonl'

    def write_snapshot(self, snapshot: Dict[str, Any]) -> None:
        payload = {'ts': datetime.now(UTC).isoformat(), 'snapshot': snapshot}
        self.latest_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    def append_strategy_candidates(self, snapshot: Dict[str, Any]) -> None:
        ts = datetime.now(UTC).isoformat()
        rows = []
        for symbol, state in snapshot.items():
            for name, strategy in state.get('strategies', {}).items():
                rows.append({
                    'ts': ts,
                    'symbol': symbol,
                    'strategy_name': name,
                    'status': strategy.get('status'),
                    'execution_ready': strategy.get('execution_ready'),
                    'last_price': strategy.get('last_price'),
                    'regime': state.get('regime_state', {}).get('regime'),
                    'regime_confidence': state.get('regime_state', {}).get('confidence'),
                })
        if not rows:
            return
        with self.runs_file.open('a', encoding='utf-8') as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def append_strategy_specs(self, specs: List[Dict[str, Any]]) -> None:
        if not specs:
            return
        with self.specs_file.open('a', encoding='utf-8') as fh:
            for spec in specs:
                fh.write(json.dumps(spec, ensure_ascii=False) + "\n")

    def append_playbook_packets(self, packets: List[Dict[str, Any]]) -> None:
        if not packets:
            return
        with self.playbook_file.open('a', encoding='utf-8') as fh:
            for packet in packets:
                fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
