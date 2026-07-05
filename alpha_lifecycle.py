from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


ALLOWED_STATES = ['draft', 'validated', 'promoted', 'shadow', 'active', 'quarantined', 'demoted', 'retired']
ALLOWED_TRANSITIONS = {
    'draft': {'validated'},
    'validated': {'promoted', 'demoted'},
    'promoted': {'shadow', 'active'},
    'shadow': {'active', 'quarantined', 'demoted'},
    'active': {'quarantined', 'demoted', 'retired'},
    'quarantined': {'active', 'retired', 'demoted'},
    'demoted': {'validated', 'retired'},
    'retired': set(),
}


@dataclass
class LifecycleTransitionResult:
    alpha_id: str
    previous_state: str
    new_state: str
    allowed: bool
    reason: str


class AlphaLifecycleStateMachine:
    def __init__(self):
        self.allowed_states = ALLOWED_STATES
        self.allowed_transitions = ALLOWED_TRANSITIONS

    def can_transition(self, previous_state: str, new_state: str) -> bool:
        return new_state in self.allowed_transitions.get(previous_state, set())

    def transition(self, alpha_id: str, previous_state: str, new_state: str, reason: str = '') -> LifecycleTransitionResult:
        allowed = self.can_transition(previous_state, new_state)
        if not allowed:
            return LifecycleTransitionResult(alpha_id, previous_state, previous_state, False, reason or 'invalid_transition')
        return LifecycleTransitionResult(alpha_id, previous_state, new_state, True, reason or 'ok')
