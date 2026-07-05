from alpha_lifecycle import AlphaLifecycleStateMachine


def test_lifecycle_accepts_valid_transition_and_blocks_invalid_one():
    sm = AlphaLifecycleStateMachine()
    ok = sm.transition('alpha_1', 'draft', 'validated', 'validation complete')
    bad = sm.transition('alpha_1', 'draft', 'active', 'skip ahead')
    assert ok.allowed is True
    assert ok.new_state == 'validated'
    assert bad.allowed is False
    assert bad.new_state == 'draft'
