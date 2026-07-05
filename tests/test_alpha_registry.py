from alpha_registry import AlphaRegistry


def test_registry_records_validation_and_lifecycle_events():
    registry = AlphaRegistry()
    registry.add_alpha_definition({'alpha_id': 'alpha_1', 'alpha_name': 'sig_1'})
    registry.record_validation_result({'alpha_id': 'alpha_1', 'validation_run_id': 'run_1', 'research_score': 90}, regime_panels=[{'alpha_id': 'alpha_1', 'regime_name': 'uptrend'}])
    registry.record_lifecycle_decision({'alpha_id': 'alpha_1', 'current_state': 'validated', 'target_state': 'promoted', 'trigger_reason': 'good', 'supporting_validation_run_id': 'run_1', 'created_at': '2026-01-01T00:00:00+00:00'})
    assert len(registry.validation_scorecards) == 1
    assert len(registry.regime_panels) == 1
    assert len(registry.lifecycle_events) == 1
