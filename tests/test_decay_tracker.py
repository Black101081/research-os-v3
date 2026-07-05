from decay_tracker import DecayTrackerV1


def test_decay_tracker_flags_large_drop():
    tracker = DecayTrackerV1()
    profile = tracker.evaluate('alpha_1', [
        {'validation_run_id': 'run_1', 'research_score': 90, 'sharpe': 2.0, 'expectancy': 0.03},
        {'validation_run_id': 'run_2', 'research_score': 60, 'sharpe': 1.2, 'expectancy': 0.015},
    ])
    assert profile is not None
    assert profile['decay_flag'] is True
    assert 'research_score_drop' in profile['decay_reason']
