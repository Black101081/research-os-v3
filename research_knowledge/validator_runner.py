from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "research_knowledge"
REPORTS = ROOT / "validation_reports"
REPORTS.mkdir(parents=True, exist_ok=True)

INDICATOR_REQUIRED = [
    "indicator_id", "family", "tier", "title", "novelty_claim", "inputs",
    "nearest_neighbors", "failure_modes", "downstream_uses", "validator_checks"
]
INDICATOR_TEMPLATE_FIELDS = [
    "thesis_type", "core_question", "intuition", "information_edge", "non_edge_warning",
    "transform_logic", "preferred_regimes", "avoid_regimes", "nearest_factors",
    "nearest_indicators", "signal_roles", "strategy_roles", "misuse_patterns",
    "validation_targets", "baseline_control", "promotion_preference"
]
STRATEGY_TEMPLATE_FIELDS = [
    "baseline_controls", "differentiated_claim", "why_now_logic", "validation_focus",
    "risk_focus", "execution_realism_assumptions", "promotion_rule", "rejection_rule",
    "failure_archetypes", "negative_knowledge_targets", "validation_targets",
    "lifecycle_requirements"
]


def score_to_decision(score: int) -> str:
    if score >= 85:
        return "PASS"
    if score >= 65:
        return "PASS_WITH_WARNINGS"
    if score >= 40:
        return "REVISE"
    return "REJECT"


def validate_indicator(entry, family_key):
    issues = []
    score = 100
    for field in INDICATOR_REQUIRED:
        if field not in entry or entry[field] in (None, "", [], {}):
            issues.append(f"missing_required:{field}")
            score -= 8
    for field in INDICATOR_TEMPLATE_FIELDS:
        if field not in entry or entry[field] in (None, "", [], {}):
            issues.append(f"missing_template:{field}")
            score -= 4
    if entry.get('nearest_neighbors') == ['research_review_required']:
        issues.append('neighbor_resolution_pending')
        score -= 6
    if 'thesis_fit' in entry.get('validator_checks', []) and 'validation_targets' not in entry:
        issues.append('thesis_fit_without_targets')
        score -= 4
    if entry.get('tier') in ('edge', 'frontier') and 'baseline_control' not in entry:
        issues.append('edge_without_baseline_control')
        score -= 5
    if 'downstream_uses' in entry and 'signal_templates' in entry['downstream_uses'] and 'signal_roles' not in entry:
        issues.append('downstream_without_signal_roles')
        score -= 4
    score = max(score, 0)
    return {
        'object_type': 'indicator',
        'family_key': family_key,
        'object_id': entry.get('indicator_id', 'UNKNOWN'),
        'score': score,
        'decision': score_to_decision(score),
        'issue_count': len(issues),
        'issues': '; '.join(issues) if issues else 'none'
    }


def validate_strategy(name, entry):
    issues = []
    score = 100
    required_now = ['source_signals', 'validation_focus', 'risk_focus', 'promotion_rule']
    for field in required_now:
        if field not in entry or entry[field] in (None, '', [], {}):
            issues.append(f'missing_required:{field}')
            score -= 10
    for field in STRATEGY_TEMPLATE_FIELDS:
        if field not in entry or entry[field] in (None, '', [], {}):
            issues.append(f'missing_template:{field}')
            score -= 6
    if 'baseline_controls' not in entry:
        issues.append('baseline_logic_missing')
        score -= 8
    if 'rejection_rule' not in entry:
        issues.append('no_explicit_rejection_rule')
        score -= 8
    if 'execution_realism_assumptions' not in entry and any(x in name for x in ['breakout', 'execution', 'trend']):
        issues.append('execution_realism_missing_for_sensitive_family')
        score -= 6
    score = max(score, 0)
    return {
        'object_type': 'strategy',
        'family_key': name,
        'object_id': name,
        'score': score,
        'decision': score_to_decision(score),
        'issue_count': len(issues),
        'issues': '; '.join(issues) if issues else 'none'
    }


def run():
    indicator_catalog = json.loads((REPO / 'expanded_indicator_catalog_v1.json').read_text(encoding='utf-8'))
    strategy_catalog = json.loads((REPO / 'expanded_strategy_catalog_v1.json').read_text(encoding='utf-8'))

    indicator_rows = []
    for family_key, family in indicator_catalog['families'].items():
        for entry in family['indicators']:
            indicator_rows.append(validate_indicator(entry, family_key))
    strategy_rows = []
    for name, entry in strategy_catalog['strategy_families'].items():
        strategy_rows.append(validate_strategy(name, entry))

    ind_df = pd.DataFrame(indicator_rows).sort_values(['decision', 'score', 'object_id'])
    strat_df = pd.DataFrame(strategy_rows).sort_values(['decision', 'score', 'object_id'])

    ind_df.to_csv(REPORTS / 'indicator_validation_report_v1.csv', index=False)
    strat_df.to_csv(REPORTS / 'strategy_validation_report_v1.csv', index=False)

    summary = {
        'indicator_total': int(len(ind_df)),
        'indicator_decisions': ind_df['decision'].value_counts().to_dict(),
        'indicator_avg_score': round(float(ind_df['score'].mean()), 2) if len(ind_df) else 0.0,
        'strategy_total': int(len(strat_df)),
        'strategy_decisions': strat_df['decision'].value_counts().to_dict(),
        'strategy_avg_score': round(float(strat_df['score'].mean()), 2) if len(strat_df) else 0.0,
        'top_indicator_issues': ind_df['issues'].str.split('; ').explode().value_counts().head(10).to_dict(),
        'top_strategy_issues': strat_df['issues'].str.split('; ').explode().value_counts().head(10).to_dict(),
    }
    (REPORTS / 'validation_summary_v1.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary

if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
