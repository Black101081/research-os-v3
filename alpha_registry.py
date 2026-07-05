from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AlphaDefinition:
    alpha_id: str
    alpha_name: str
    source_type: str
    symbol_scope: str | list[str]
    universe_scope: str | list[str]
    timeframe: str
    regime_scope: list[str]
    factor_dependencies: list[str]
    indicator_dependencies: list[str]
    signal_template_family: str
    signal_expression: str
    parameter_set: Dict[str, Any]
    thesis_summary: str
    lineage_parent_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    created_by: str = 'system'


class AlphaRegistry:
    def __init__(self):
        self.alpha_definitions: Dict[str, Dict[str, Any]] = {}
        self.validation_scorecards: List[Dict[str, Any]] = []
        self.regime_panels: List[Dict[str, Any]] = []
        self.decay_profiles: List[Dict[str, Any]] = []
        self.lifecycle_events: List[Dict[str, Any]] = []
        self.revalidation_tasks: List[Dict[str, Any]] = []

    def add_alpha_definition(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(payload)
        self.alpha_definitions[record['alpha_id']] = record
        return record

    def add_validation_scorecard(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(payload)
        self.validation_scorecards.append(record)
        return record

    def add_regime_panel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(payload)
        self.regime_panels.append(record)
        return record

    def add_decay_profile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(payload)
        self.decay_profiles.append(record)
        return record

    def add_lifecycle_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(payload)
        self.lifecycle_events.append(record)
        return record

    def record_validation_result(self, scorecard: Dict[str, Any], regime_panels: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        saved = self.add_validation_scorecard(scorecard)
        for panel in regime_panels or []:
            self.add_regime_panel(panel)
        return saved

    def record_lifecycle_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            'alpha_id': decision['alpha_id'],
            'event_type': decision['target_state'],
            'previous_state': decision.get('current_state'),
            'new_state': decision.get('target_state'),
            'trigger_reason': decision.get('trigger_reason'),
            'supporting_validation_run_id': decision.get('supporting_validation_run_id'),
            'created_at': decision.get('created_at', now_iso()),
        }
        return self.add_lifecycle_event(event)

    def latest_scorecards(self) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for row in self.validation_scorecards:
            latest[row['alpha_id']] = row
        return latest
