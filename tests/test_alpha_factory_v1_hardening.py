import json
from pathlib import Path
from alpha_factory_demo_v1 import run_alpha_factory_demo_v1
from alpha_factory_runner import AlphaFactoryRunner


def test_demo_summary_contains_healthcheck_and_briefs(tmp_path):
    payload = run_alpha_factory_demo_v1(tmp_path / 'demo_run', candidate_limit=3)
    summary = payload['summary']
    assert 'healthcheck' in summary
    assert summary['healthcheck']['alpha_count'] == 3
    assert Path(summary['brief_json_path']).exists()
    assert Path(summary['brief_md_path']).exists()


def test_runner_healthcheck_reports_registry_counts(tmp_path):
    runner = AlphaFactoryRunner(tmp_path / 'registry_store')
    runner.registry.add_alpha_definition({'alpha_id': 'alpha_1', 'alpha_name': 'sig_1'})
    runner.registry.add_validation_scorecard({'alpha_id': 'alpha_1', 'research_score': 10})
    runner.registry.revalidation_tasks = [{'task_id': 't1'}]
    health = runner.healthcheck()
    assert health['alpha_count'] == 1
    assert health['validation_scorecard_count'] == 1
    assert health['revalidation_task_count'] == 1
