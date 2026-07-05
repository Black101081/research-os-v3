from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RevalidationSchedulerV1:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {
            'quarantined_priority': 'high',
            'demoted_priority': 'medium',
            'decay_priority': 'high',
            'default_due_hours': 24,
        }

    def create_tasks(self, alpha_definitions: Dict[str, Dict[str, Any]], lifecycle_events: List[Dict[str, Any]], decay_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks: Dict[str, Dict[str, Any]] = {}
        for event in lifecycle_events:
            new_state = event.get('new_state')
            alpha_id = event.get('alpha_id')
            if new_state not in {'quarantined', 'demoted'}:
                continue
            tasks[alpha_id] = {
                'task_id': f'revalidate_{alpha_id}_{new_state}',
                'alpha_id': alpha_id,
                'alpha_name': alpha_definitions.get(alpha_id, {}).get('alpha_name'),
                'reason': f'lifecycle_{new_state}',
                'priority': self.config['quarantined_priority'] if new_state == 'quarantined' else self.config['demoted_priority'],
                'due_hours': self.config['default_due_hours'],
                'created_at': now_iso(),
            }
        for profile in decay_profiles:
            if not profile.get('decay_flag'):
                continue
            alpha_id = profile['alpha_id']
            tasks[alpha_id] = {
                'task_id': f'revalidate_{alpha_id}_decay',
                'alpha_id': alpha_id,
                'alpha_name': alpha_definitions.get(alpha_id, {}).get('alpha_name'),
                'reason': f"decay:{profile.get('decay_reason')}",
                'priority': self.config['decay_priority'],
                'due_hours': self.config['default_due_hours'],
                'created_at': now_iso(),
            }
        return list(tasks.values())
