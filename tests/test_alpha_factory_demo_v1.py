import json
from pathlib import Path
from alpha_factory_demo_v1 import run_alpha_factory_demo_v1


def test_alpha_factory_demo_v1_runs_end_to_end(tmp_path):
    payload = run_alpha_factory_demo_v1(tmp_path / 'demo_run', candidate_limit=3)
    summary = payload['summary']
    assert summary['candidate_count'] == 3
    assert summary['registered_alpha_count'] == 3
    assert summary['validation_scorecard_count'] >= 3
    assert Path(summary['brief_json_path']).exists()
    assert Path(summary['brief_md_path']).exists()
    assert 'decisions' in payload
