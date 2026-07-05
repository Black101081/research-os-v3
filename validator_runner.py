from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List

BASE = Path(__file__).resolve().parent
RK = BASE / 'research_knowledge'

REQUIRED_FACTOR_FIELDS = ['factor_id','tier','title','novelty_claim','failure_modes','validator_checks']
REQUIRED_INDICATOR_FIELDS = ['indicator_id','tier','title','novelty_claim','inputs','failure_modes','validator_checks']
VALID_TIERS = {'core','edge','frontier'}


def _score_text_novelty(text: str) -> int:
    text = (text or '').lower()
    score = 0
    if any(k in text for k in ['holistic','composite','quality','fragility','asymmetric','latent','curvature','hazard','trap','readiness']):
        score += 2
    if any(k in text for k in ['not just','instead of','rather than','separates','combines','quality of']):
        score += 2
    if len(text.split()) >= 6:
        score += 1
    return min(score, 5)


def _score_failure_clarity(failure_modes: List[str]) -> int:
    if not failure_modes:
        return 0
    joined = ' '.join(failure_modes).lower()
    score = 1
    if any(k in joined for k in ['trend','chop','liquidity','noise','shock','instability']):
        score += 2
    if len(joined.split()) >= 6:
        score += 2
    return min(score, 5)


def _research_score(item: Dict[str, Any]) -> Dict[str, int]:
    novelty = _score_text_novelty(item.get('novelty_claim', ''))
    interpretability = 4 if item.get('title') and item.get('novelty_claim') else 2
    falsifiability = 4 if item.get('validator_checks') else 2
    portability = 4 if item.get('tier') in {'core','edge'} else 3
    execution_relevance = 4 if any(k in ' '.join(item.get('downstream_uses', [])).lower() for k in ['signal','strategy','validation']) else 2
    failure_clarity = _score_failure_clarity(item.get('failure_modes', []))
    total = novelty + interpretability + falsifiability + portability + execution_relevance + failure_clarity
    return {
        'interpretability': interpretability,
        'novelty': novelty,
        'falsifiability': falsifiability,
        'portability': portability,
        'execution_relevance': execution_relevance,
        'failure_clarity': failure_clarity,
        'total': total,
    }


def _decision(total: int) -> str:
    if total >= 24:
        return 'PASS'
    if total >= 18:
        return 'PASS_WITH_WARNINGS'
    if total >= 12:
        return 'REVISE'
    return 'REJECT'


def _validate_factor_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    rows = []
    ids = set()
    for fam_key, fam in catalog['families'].items():
        for item in fam['factors']:
            missing = [f for f in REQUIRED_FACTOR_FIELDS if f not in item]
            if missing:
                issues.append({'type':'factor_missing_fields','id': item.get('factor_id'), 'missing': missing})
            if item.get('tier') not in VALID_TIERS:
                issues.append({'type':'factor_invalid_tier','id': item.get('factor_id'), 'tier': item.get('tier')})
            if item.get('factor_id') in ids:
                issues.append({'type':'factor_duplicate_id','id': item.get('factor_id')})
            ids.add(item.get('factor_id'))
            scores = _research_score(item)
            rows.append({'id': item.get('factor_id'), 'family': fam_key, 'tier': item.get('tier'), 'decision': _decision(scores['total']), 'scores': scores})
    return {'issues': issues, 'rows': rows}


def _validate_indicator_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    rows = []
    ids = set()
    for fam_key, fam in catalog['families'].items():
        for item in fam['indicators']:
            missing = [f for f in REQUIRED_INDICATOR_FIELDS if f not in item]
            if missing:
                issues.append({'type':'indicator_missing_fields','id': item.get('indicator_id'), 'missing': missing})
            if item.get('tier') not in VALID_TIERS:
                issues.append({'type':'indicator_invalid_tier','id': item.get('indicator_id'), 'tier': item.get('tier')})
            if item.get('indicator_id') in ids:
                issues.append({'type':'indicator_duplicate_id','id': item.get('indicator_id')})
            ids.add(item.get('indicator_id'))
            scores = _research_score(item)
            rows.append({'id': item.get('indicator_id'), 'family': fam_key, 'tier': item.get('tier'), 'decision': _decision(scores['total']), 'scores': scores})
    return {'issues': issues, 'rows': rows}



def _validate_signal_registry(registry: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    rows = []
    families = registry.get('families', {})
    for fam_key, fam in families.items():
        for item in fam.get('signals', []):
            signal_id = item.get('signal_id')
            missing = [f for f in ['signal_id','template_family', 'preferred_regimes', 'avoid_regimes', 'required_factors', 'required_indicators', 'thesis', 'trigger_logic', 'invalidation_logic', 'execution_note', 'novelty_claim'] if f not in item]
            if missing:
                issues.append({'type': 'signal_missing_fields', 'id': signal_id, 'missing': missing})
            novelty_text = f"{item.get('template_family','')} {item.get('novelty_claim','')}"
            scores = {
                'interpretability': 4 if item.get('template_family') and item.get('thesis') else 2,
                'novelty': _score_text_novelty(novelty_text),
                'falsifiability': 4 if ('required_factors' in item and 'required_indicators' in item and item.get('invalidation_logic')) else 2,
                'portability': 4 if item.get('template_family') in {'breakout','mean_reversion','trend_continuation','volatility_transition','volatility_exhaustion','execution_aware'} else 3,
                'execution_relevance': 4,
                'failure_clarity': 4 if item.get('avoid_regimes') and item.get('invalidation_logic') else 1,
            }
            total = sum(scores.values())
            rows.append({'id': signal_id, 'family': item.get('template_family'), 'tier': item.get('tier','template'), 'decision': _decision(total), 'scores': {**scores, 'total': total}})
    return {'issues': issues, 'rows': rows}


def _validate_strategy_registry(registry: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    rows = []
    family_mappings = registry.get('strategy_families', {})
    stage_order = registry.get('target', {})
    for family, item in family_mappings.items():
        missing = [f for f in ['source_signals','validation_focus', 'risk_focus', 'promotion_rule'] if f not in item]
        if missing:
            issues.append({'type': 'strategy_missing_fields', 'id': family, 'missing': missing})
        novelty_text = ' '.join(item.get('validation_focus', []) + item.get('risk_focus', []))
        scores = {
            'interpretability': 4,
            'novelty': _score_text_novelty(novelty_text),
            'falsifiability': 4 if item.get('validation_focus') else 2,
            'portability': 4,
            'execution_relevance': 5,
            'failure_clarity': 3 if item.get('risk_focus') else 1,
        }
        total = sum(scores.values())
        rows.append({'id': family, 'family': family, 'tier': 'strategy_family', 'decision': _decision(total), 'scores': {**scores, 'total': total}})
    return {'issues': issues, 'rows': rows}

def run_validator() -> Dict[str, Any]:
    factor_catalog = json.loads((RK / 'expanded_factor_catalog_v1.json').read_text())
    indicator_catalog = json.loads((RK / 'expanded_indicator_catalog_v1.json').read_text())
    signal_registry = json.loads((RK / 'expanded_signal_catalog_v1.json').read_text())
    strategy_registry = json.loads((RK / 'expanded_strategy_catalog_v1.json').read_text())
    factor_result = _validate_factor_catalog(factor_catalog)
    indicator_result = _validate_indicator_catalog(indicator_catalog)
    signal_result = _validate_signal_registry(signal_registry)
    strategy_result = _validate_strategy_registry(strategy_registry)
    summary = {
        'factor_count': len(factor_result['rows']),
        'indicator_count': len(indicator_result['rows']),
        'factor_issue_count': len(factor_result['issues']),
        'indicator_issue_count': len(indicator_result['issues']),
        'signal_count': len(signal_result['rows']),
        'strategy_family_count': len(strategy_result['rows']),
        'signal_issue_count': len(signal_result['issues']),
        'strategy_issue_count': len(strategy_result['issues']),
        'factor_decisions': {},
        'indicator_decisions': {},
        'signal_decisions': {},
        'strategy_decisions': {},
    }
    for row in factor_result['rows']:
        summary['factor_decisions'][row['decision']] = summary['factor_decisions'].get(row['decision'], 0) + 1
    for row in indicator_result['rows']:
        summary['indicator_decisions'][row['decision']] = summary['indicator_decisions'].get(row['decision'], 0) + 1
    for row in signal_result['rows']:
        summary['signal_decisions'][row['decision']] = summary['signal_decisions'].get(row['decision'], 0) + 1
    for row in strategy_result['rows']:
        summary['strategy_decisions'][row['decision']] = summary['strategy_decisions'].get(row['decision'], 0) + 1
    report = {'summary': summary, 'factor_validation': factor_result, 'indicator_validation': indicator_result, 'signal_validation': signal_result, 'strategy_validation': strategy_result}
    out = BASE / 'runtime' / 'research_validator_report.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(run_validator()['summary'], ensure_ascii=False, indent=2))
