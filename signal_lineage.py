from __future__ import annotations

from typing import Any, Dict


def build_lineage_record(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'signal_candidate_id': candidate.get('signal_candidate_id'),
        'template_family': candidate.get('template_family'),
        'source_expression_ids': candidate.get('source_expression_ids', []),
        'lineage_metadata': candidate.get('lineage_metadata', {}),
    }
