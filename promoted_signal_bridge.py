from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List


class PromotedSignalBridge:
    def __init__(self, store_base: str | Path | None = None):
        self.workspace_root = Path(__file__).resolve().parent
        if store_base:
            self.store_bases = [Path(store_base)]
        else:
            runtime_dir = self.workspace_root / 'runtime'
            runtime_dir.mkdir(parents=True, exist_ok=True)
            self.store_bases = [
                runtime_dir,
                self.workspace_root / 'sandbox_test_reports' / 'alpha_factory_demo_v1' / 'registry_store'
            ]

    def load_promoted_alphas(self) -> List[Dict[str, Any]]:
        active_definitions_path = None
        active_events_path = None
        
        for base in self.store_bases:
            defn_path = base / 'alpha_definitions.jsonl'
            evt_path = base / 'lifecycle_events.jsonl'
            if defn_path.exists() and evt_path.exists():
                active_definitions_path = defn_path
                active_events_path = evt_path
                break
                
        if not active_definitions_path or not active_events_path:
            return []

        # 1. Load latest state of each alpha
        latest_states: Dict[str, str] = {}
        try:
            with active_events_path.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    alpha_id = event.get('alpha_id')
                    target_state = event.get('target_state')
                    if alpha_id and target_state:
                        latest_states[alpha_id] = target_state
        except Exception:
            pass

        # 2. Load alpha definitions
        promoted_alphas = []
        try:
            with active_definitions_path.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    defn = json.loads(line)
                    alpha_id = defn.get('alpha_id')
                    if alpha_id and latest_states.get(alpha_id) == 'promoted':
                        promoted_alphas.append(defn)
        except Exception:
            pass

        return promoted_alphas
