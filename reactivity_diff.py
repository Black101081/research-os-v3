from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _changed_keys(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    keys = sorted(set((before or {}).keys()) | set((after or {}).keys()))
    return [k for k in keys if (before or {}).get(k) != (after or {}).get(k)]


def _changed_named_objects(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    names = sorted(set((before or {}).keys()) | set((after or {}).keys()))
    return [name for name in names if (before or {}).get(name) != (after or {}).get(name)]


def build_reactivity_diff_v1(
    symbol: str,
    message_type: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
    reactive_source: str | None = None,
) -> Dict[str, Any]:
    factors_changed = _changed_keys(before.get('factors', {}), after.get('factors', {}))
    indicators_changed = _changed_keys(before.get('indicators', {}), after.get('indicators', {}))
    signals_changed = _changed_named_objects(before.get('signals', {}), after.get('signals', {}))
    strategies_changed = _changed_named_objects(before.get('strategies', {}), after.get('strategies', {}))
    risk_packets_changed = _changed_named_objects(before.get('risk_packets', {}), after.get('risk_packets', {}))
    validation_changed = before.get('validation_packet') != after.get('validation_packet')
    regime_changed = before.get('regime_state') != after.get('regime_state')
    current_bar_changed = before.get('current_bar') != after.get('current_bar')
    return {
        'symbol': symbol,
        'message_type': message_type,
        'processed_at': now_iso(),
        'current_bar_changed': current_bar_changed,
        'factors_changed': factors_changed,
        'indicators_changed': indicators_changed,
        'regime_changed': regime_changed,
        'signals_changed': signals_changed,
        'strategies_changed': strategies_changed,
        'risk_changed': bool(risk_packets_changed),
        'risk_packets_changed': risk_packets_changed,
        'validation_changed': validation_changed,
        'reactive_source': reactive_source or 'unknown',
    }
