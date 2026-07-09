#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from alpha_factory_runner import AlphaFactoryRunner
from signal_generator import SignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("continuous_alpha_factory.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("ContinuousAlphaFactory")


def load_catalogs(base_dir: Path) -> tuple[Dict[str, Any], Dict[str, Any]]:
    factor_catalog_path = base_dir / 'factor_catalog_v1.json'
    template_library_path = base_dir / 'signal_template_library_v1.json'
    
    if not factor_catalog_path.exists() or not template_library_path.exists():
        raise FileNotFoundError("Missing factor_catalog_v1.json or signal_template_library_v1.json in root directory.")
        
    factor_catalog = json.loads(factor_catalog_path.read_text(encoding='utf-8'))
    template_library = json.loads(template_library_path.read_text(encoding='utf-8'))
    return factor_catalog, template_library


def build_alpha_definitions(candidates: List[Dict[str, Any]], start_index: int = 1) -> List[Dict[str, Any]]:
    alpha_defs = []
    for i, c in enumerate(candidates, start=start_index):
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


def run_iteration(runner: AlphaFactoryRunner, factor_catalog: Dict[str, Any], template_library: Dict[str, Any], candidate_limit: int = 3) -> Dict[str, Any]:
    logger.info("Starting a new Alpha Factory iteration...")
    
    # 1. Generate new candidates
    generator = SignalGenerator(factor_catalog, template_library)
    candidates = generator.generate_candidates()[:candidate_limit]
    logger.info(f"Generated {len(candidates)} new candidates from templates.")
    
    # 2. Map candidate indices dynamically based on existing registered alphas
    existing_alpha_count = len(runner.registry.alpha_definitions)
    alpha_defs = build_alpha_definitions(candidates, start_index=existing_alpha_count + 1)
    
    # 3. Register the new candidates
    runner.register_alphas(alpha_defs)
    logger.info(f"Registered {len(alpha_defs)} new Alpha definitions in the registry.")
    
    # 4. Perform real validation on new candidates
    logger.info("Executing real validation on candidates...")
    ranked = runner.run_real_validation(candidates)
    
    # 5. Retrieve current states from lifecycle events history
    current_states: Dict[str, str] = {}
    for event in runner.registry.lifecycle_events:
        alpha_id = event.get('alpha_id')
        new_state = event.get('new_state')
        if alpha_id and new_state:
            current_states[alpha_id] = new_state
            
    # Assign default state 'validated' for any new definitions that haven't transitioned yet
    for alpha in alpha_defs:
        alpha_id = alpha['alpha_id']
        if alpha_id not in current_states:
            current_states[alpha_id] = 'validated'
            
    # 6. Execute promotion / demotion decisions
    logger.info("Running promotion and diversification engine...")
    decisions = runner.run_promotion(current_states=current_states)
    for dec in decisions:
        logger.info(f"Alpha {dec['alpha_id']}: {dec.get('current_state', 'unknown')} -> {dec.get('target_state', 'unknown')} | Reason: {dec.get('decision_reason', 'none')}")
        
    # 7. Scan for alpha decay
    logger.info("Scanning for strategy performance decay...")
    decay_profiles = runner.run_decay_scan()
    if decay_profiles:
        logger.info(f"Generated {len(decay_profiles)} decay profiles.")
        
    # 8. Rebuild revalidation schedule
    revalidation_tasks = runner.build_revalidation_tasks()
    
    # Summary of this iteration
    summary = {
        'timestamp': time.time(),
        'candidate_count': len(candidates),
        'registered_alpha_count': len(alpha_defs),
        'validation_scorecard_count': len(runner.registry.validation_scorecards),
        'promoted_count': sum(1 for d in decisions if d.get('target_state') == 'promoted'),
        'demoted_count': sum(1 for d in decisions if d.get('target_state') == 'demoted'),
        'quarantined_count': sum(1 for d in decisions if d.get('target_state') == 'quarantined'),
        'decay_profile_count': len(decay_profiles),
        'revalidation_task_count': len(revalidation_tasks),
    }
    logger.info(f"Iteration finished. Promoted: {summary['promoted_count']}, Demoted: {summary['demoted_count']}, Decay: {summary['decay_profile_count']}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Continuous Alpha Factory & Rotation Loop Service")
    parser.add_argument("--loop", action="store_true", help="Run indefinitely in a loop")
    parser.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    parser.add_argument("--interval", type=int, default=1800, help="Sleep interval between loop iterations in seconds (default: 1800s / 30m)")
    parser.add_argument("--candidates", type=int, default=3, help="Max candidates per iteration (default: 3)")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    registry_dir = base_dir / 'runtime'
    registry_dir.mkdir(parents=True, exist_ok=True)
    
    factor_catalog, template_library = load_catalogs(base_dir)
    runner = AlphaFactoryRunner(registry_dir)
    
    if args.once or (not args.loop):
        logger.info("Executing a single dry-run iteration...")
        run_iteration(runner, factor_catalog, template_library, candidate_limit=args.candidates)
        logger.info("Dry-run completed successfully.")
    elif args.loop:
        logger.info(f"Starting continuous loop service. Sleep interval: {args.interval} seconds.")
        try:
            while True:
                run_iteration(runner, factor_catalog, template_library, candidate_limit=args.candidates)
                logger.info(f"Sleeping for {args.interval} seconds before next run...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Service stopped by user (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
