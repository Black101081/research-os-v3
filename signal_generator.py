from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_id(seed: str) -> str:
    return sha1(seed.encode('utf-8')).hexdigest()[:16]


class SignalGenerator:
    def __init__(self, factor_catalog: Dict[str, Any], template_library: Dict[str, Any], config: Dict[str, Any] | None = None):
        self.factor_catalog = factor_catalog
        self.template_library = template_library
        self.config = config or template_library.get('generation_defaults', {})

    def factor_ids(self) -> List[str]:
        ids: List[str] = []
        for family in self.factor_catalog.get('families', []):
            for factor in family.get('factors', []):
                ids.append(factor['factor_id'])
        return ids

    def _build_expression(self, required_inputs: List[str], family: str) -> str:
        parts = []
        for factor_id in required_inputs:
            if factor_id == 'BollingerWidth':
                parts.append("BollingerWidth < 0.03")
            elif factor_id == 'live_ret_from_last_close':
                parts.append("live_ret_from_last_close > 0.001")
            elif factor_id == 'zscore_close_20':
                parts.append("zscore_close_20 < -1.5")
            elif factor_id == 'micro_volatility_20':
                if family == 'volatility_event':
                    parts.append("micro_volatility_20 > 0.002")
                else:
                    parts.append("micro_volatility_20 < 0.004")
            elif factor_id == 'MACD':
                if 'MACD_signal' in required_inputs:
                    parts.append("MACD > MACD_signal")
                else:
                    parts.append("MACD > 0")
            elif factor_id == 'MACD_signal':
                continue
            elif factor_id == 'ema_spread_8_21':
                parts.append("ema_spread_8_21 > 0")
            elif factor_id == 'spread_bps':
                parts.append("spread_bps < 8")
            elif factor_id == 'tick_ret_5':
                parts.append("tick_ret_5 > 0")
            elif factor_id == 'trade_flow_imbalance_20':
                parts.append("trade_flow_imbalance_20 > 0.1")
            else:
                parts.append(f"{factor_id} > 0")
        return " and ".join(parts)

    def generate_candidates(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        max_candidates = int(self.config.get('max_candidates_per_batch', 100))
        known = set(self.factor_ids())
        for template in self.template_library.get('template_families', []):
            required = template.get('required_inputs', [])
            if not all(r in known for r in required):
                continue
            family = template.get('family')
            expr = self._build_expression(required, family)
            seed = f"{template['template_id']}|{expr}"
            candidates.append({
                'signal_candidate_id': _candidate_id(seed),
                'signal_name': f"{family}_{len(candidates)+1}",
                'source_expression_ids': required,
                'template_family': family,
                'regime_scope': template.get('default_regime_scope', []),
                'symbol_scope': 'any',
                'timeframe': '1m',
                'parameter_set': {'template_id': template['template_id']},
                'trigger_definition': expr,
                'confirmation_definition': None,
                'invalidation_definition': None,
                'thesis_summary': template.get('thesis_template', {}).get('what_edge_it_targets'),
                'tags': [family, 'generated'],
                'created_at': now_iso(),
                'lineage_metadata': {
                    'template_id': template['template_id'],
                    'generation_rule_id': 'default_v1_rule',
                },
                'validation_status': 'draft',
            })
            if len(candidates) >= max_candidates:
                break
        return candidates
