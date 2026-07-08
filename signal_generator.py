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
            elif factor_id == 'bb_pct_b':
                parts.append("bb_pct_b < 0.05")
            elif factor_id == 'rsi_14':
                parts.append("rsi_14 < 30")
            elif factor_id == 'price_vs_sma20':
                parts.append("abs(price_vs_sma20) < 0.01")
            elif factor_id == 'volatility_ratio_5_20':
                parts.append("volatility_ratio_5_20 < 0.7")
            elif factor_id == 'atr_pct_14':
                parts.append("atr_pct_14 > 0.01")
            elif factor_id == 'momentum_divergence':
                parts.append("momentum_divergence != 0")
            elif factor_id == 'trade_flow_imbalance_50':
                parts.append("trade_flow_imbalance_50 > 0.2")
            elif factor_id == 'large_trade_ratio':
                parts.append("large_trade_ratio > 0.15")
            elif factor_id == 'btc_ret_1':
                parts.append("abs(btc_ret_1) > 0.003")
            elif factor_id == 'market_correlation_20':
                parts.append("market_correlation_20 > 0.7")
            elif factor_id == 'book_imbalance_5':
                parts.append("abs(book_imbalance_5) > 0.15")
            elif factor_id == 'book_imbalance_10':
                parts.append("abs(book_imbalance_10) > 0.10")
            elif factor_id == 'book_imbalance_20':
                parts.append("abs(book_imbalance_20) > 0.10")
            else:
                parts.append(f"{factor_id} > 0")
        return " and ".join(parts)

    def _build_confirmation(self, family: str) -> str:
        if family == 'breakout':
            return "RelativeVolume >= 1.2 and abs(TradeFlowImbalance) >= 0.2"
        elif family == 'mean_reversion':
            return "rsi_14 <= 30 or rsi_14 >= 70"
        elif family == 'continuation':
            return "MACD_hist > 0 and RelativeVolume >= 1.0"
        elif family == 'volatility_event':
            return "rel_volume_20 >= 2.0 and volatility_ratio_5_20 > 1.5"
        elif family == 'order_flow':
            return "trade_flow_imbalance_50 > 0.2 or trade_flow_imbalance_50 < -0.2"
        elif family == 'cross_asset':
            return "market_correlation_20 >= 0.7"
        elif family == 'divergence':
            return "rsi_14 <= 35 or rsi_14 >= 65"
        else:
            return "RelativeVolume >= 1.0"

    def _build_invalidation(self, family: str) -> str:
        if family == 'breakout':
            return "BollingerWidth > 0.3 or SpreadBps > 10.0"
        elif family == 'mean_reversion':
            return "abs(zscore_close_20) > 3.0 or volatility_ratio_5_20 > 1.5"
        elif family == 'continuation':
            return "MACD <= MACD_signal or price_vs_sma20 < -0.02"
        elif family == 'volatility_event':
            return "SpreadBps > 10.0"
        elif family == 'order_flow':
            return "large_trade_ratio < 0.05 or SpreadBps > 8.0"
        elif family == 'cross_asset':
            return "market_correlation_20 < 0.5 or abs(btc_ret_1) < 0.001"
        elif family == 'divergence':
            return "price_vs_sma20 < -0.02 or price_vs_sma20 > 0.02"
        else:
            return "price_vs_sma20 < -0.02 or price_vs_sma20 > 0.02"

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
            confirm_expr = self._build_confirmation(family)
            invalidate_expr = self._build_invalidation(family)
            seed = f"{template['template_id']}|{expr}"
            
            thesis_template = template.get('thesis_template', {})
            thesis_sum = thesis_template.get('what_edge_it_targets', 'Generated thesis')
            entry_sum = thesis_template.get('entry_logic', 'Generated entry logic')
            
            confirm_guidelines = template.get('confirmation_logic_guidelines', [])
            confirm_sum = confirm_guidelines[0] if confirm_guidelines else "Confirm signal via quality filters"
            
            invalidate_guidelines = template.get('invalidation_logic_guidelines', [])
            invalidate_sum = invalidate_guidelines[0] if invalidate_guidelines else "Invalidate signal if structure fails"
            
            tier = "B" if family in ["pattern", "divergence"] else "A"
            min_confirm = 0.6 if family in ["breakout", "continuation", "order_flow"] else 0.5
            
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
                'confirmation_definition': confirm_expr,
                'invalidation_definition': invalidate_expr,
                'thesis_summary': thesis_sum,
                'entry_logic_summary': entry_sum,
                'confirmation_summary': confirm_sum,
                'invalidation_summary': invalidate_sum,
                'quality_tier': tier,
                'min_confirmation_score': min_confirm,
                'min_invalidation_score': 0.5,
                'execution_sensitivity_summary': "Highly sensitive to spreads" if family in ["breakout", "order_flow", "volatility_event"] else "Medium sensitivity",
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
