from real_validation_bridge import RealValidationBridgeV1


def test_real_validation_bridge_builds_observations_from_runtime_artifacts():
    bridge = RealValidationBridgeV1()
    observations = bridge.build_observations([
        {'alpha_id': 'alpha_1'},
        {'alpha_id': 'alpha_2'},
    ])
    assert observations
    assert 'alpha_1' in observations
    assert 'expectancy' in observations['alpha_1']
    assert 'live_context' in observations['alpha_1']
