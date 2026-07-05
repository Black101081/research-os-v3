from __future__ import annotations

from typing import Any, Dict, List, Tuple


def normalize_expression(expr: str) -> str:
    return ' '.join((expr or '').lower().split())


class CandidatePruner:
    def prune(self, candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kept: List[Dict[str, Any]] = []
        dropped: List[Dict[str, Any]] = []
        seen = set()
        for c in candidates:
            norm = normalize_expression(c.get('trigger_definition', ''))
            if not norm or norm in seen:
                dropped.append({**c, 'drop_reason': 'duplicate_or_empty_expression'})
                continue
            seen.add(norm)
            kept.append(c)
        return kept, dropped
