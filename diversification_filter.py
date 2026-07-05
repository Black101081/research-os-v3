from __future__ import annotations

from typing import Any, Dict, List


class DiversificationFilterV1:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {
            'max_active_per_family': 1,
            'promotion_targets': {'promoted', 'active'},
            'active_states': {'promoted', 'shadow', 'active'},
        }

    def filter_decisions(self, alpha_definitions: List[Dict[str, Any]], decisions: List[Dict[str, Any]], current_states: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
        current_states = current_states or {}
        alpha_map = {a['alpha_id']: a for a in alpha_definitions}
        active_family_counts: Dict[str, int] = {}
        for alpha in alpha_definitions:
            family = alpha.get('signal_template_family', 'unknown')
            state = current_states.get(alpha['alpha_id'], 'validated')
            if state in self.config['active_states']:
                active_family_counts[family] = active_family_counts.get(family, 0) + 1

        filtered: List[Dict[str, Any]] = []
        for decision in decisions:
            item = dict(decision)
            alpha = alpha_map.get(item['alpha_id'], {})
            family = alpha.get('signal_template_family', 'unknown')
            target = item.get('target_state')
            item['diversification_pass'] = True
            item['diversification_reason'] = None
            if target in self.config['promotion_targets']:
                current_count = active_family_counts.get(family, 0)
                if current_count >= int(self.config['max_active_per_family']):
                    item['diversification_pass'] = False
                    item['diversification_reason'] = 'family_overlap_limit'
                    item['target_state'] = item.get('current_state', 'validated')
                else:
                    active_family_counts[family] = current_count + 1
            filtered.append(item)
        return filtered
