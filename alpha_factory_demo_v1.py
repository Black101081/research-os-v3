from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from alpha_factory_runner import AlphaFactoryRunner
from signal_generator import SignalGenerator


def load_catalogs(base: Path) -> tuple[Dict[str, Any], Dict[str, Any]]:
    factor_catalog = json.loads((base / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((base / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    return factor_catalog, template_library


def build_alpha_definitions(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alpha_defs = []
    for i, c in enumerate(candidates, start=1):
        alpha_defs.append({
            'alpha_id': f'alpha_{i}',
            'alpha_name': c['signal_name'],
            'source_type': 'generated',
            'symbol_scope': 'BTC',
            'universe_scope': 'crypto',
            'timeframe': c['timeframe'],
            'regime_scope': c['regime_scope'],
            'factor_dependencies': c['source_expression_ids'],
            'indicator_dependencies': [],
            'signal_template_family': c['template_family'],
            'signal_expression': c['trigger_definition'],
            'parameter_set': c['parameter_set'],
            'thesis_summary': c['thesis_summary'],
            'lineage_parent_ids': [],
            'created_by': 'system',
        })
    return alpha_defs


def run_alpha_factory_demo_v1(output_base: str | Path | None = None, candidate_limit: int = 3) -> Dict[str, Any]:
    base = Path(__file__).resolve().parent
    output_base = Path(output_base) if output_base else base / 'sandbox_test_reports' / 'alpha_factory_demo_v1'
    output_base.mkdir(parents=True, exist_ok=True)

    factor_catalog, template_library = load_catalogs(base)
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()[:candidate_limit]
    runner = AlphaFactoryRunner(output_base / 'registry_store')
    alpha_defs = build_alpha_definitions(candidates)
    runner.register_alphas(alpha_defs)

    ranked = runner.run_real_validation(candidates)
    current_states = {alpha['alpha_id']: 'validated' for alpha in alpha_defs}
    decisions = runner.run_promotion(current_states=current_states)

    if ranked:
        top = ranked[0]
        runner.registry.add_validation_scorecard({
            'alpha_id': top['alpha_id'],
            'validation_run_id': 'demo_followup_window',
            'research_score': max(0.0, float(top.get('research_score', 0.0)) - 35.0),
            'sharpe': max(0.0, float(top.get('sharpe', 0.0)) - 0.8),
            'expectancy': max(0.0, float(top.get('expectancy', 0.0)) - 0.01),
        })

    decay_profiles = runner.run_decay_scan()
    revalidation_tasks = runner.build_revalidation_tasks()
    brief_paths = runner.generate_research_brief('alpha_factory_demo_v1_brief')
    health = runner.healthcheck()

    summary = {
        'candidate_count': len(candidates),
        'registered_alpha_count': len(alpha_defs),
        'validation_scorecard_count': len(runner.registry.validation_scorecards),
        'top_ranked_alpha': ranked[0]['alpha_id'] if ranked else None,
        'top_research_score': ranked[0]['research_score'] if ranked else None,
        'promoted_count': sum(1 for d in decisions if d.get('target_state') == 'promoted'),
        'demoted_count': sum(1 for d in decisions if d.get('target_state') == 'demoted'),
        'quarantined_count': sum(1 for d in decisions if d.get('target_state') == 'quarantined'),
        'decay_profile_count': len(decay_profiles),
        'revalidation_task_count': len(revalidation_tasks),
        'brief_json_path': brief_paths['json_path'],
        'brief_md_path': brief_paths['md_path'],
        'healthcheck': health,
    }
    out = {
        'summary': summary,
        'ranked_scorecards': ranked,
        'decisions': decisions,
        'decay_profiles': decay_profiles,
        'revalidation_tasks': revalidation_tasks,
        'brief_paths': brief_paths,
    }
    summary_path = output_base / 'alpha_factory_demo_v1_summary.json'
    summary_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='Run Alpha Factory demo v1 end-to-end')
    parser.add_argument('--output-base', default=None)
    parser.add_argument('--candidate-limit', type=int, default=3)
    args = parser.parse_args()
    payload = run_alpha_factory_demo_v1(output_base=args.output_base, candidate_limit=args.candidate_limit)
    print(json.dumps(payload['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
