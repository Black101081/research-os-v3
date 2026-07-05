from revalidation_scheduler import RevalidationSchedulerV1


def test_revalidation_scheduler_creates_tasks_for_demotion_and_decay():
    tasks = RevalidationSchedulerV1().create_tasks(
        {'alpha_1': {'alpha_name': 'sig_1'}, 'alpha_2': {'alpha_name': 'sig_2'}},
        [{'alpha_id': 'alpha_1', 'new_state': 'demoted'}],
        [{'alpha_id': 'alpha_2', 'decay_flag': True, 'decay_reason': 'research_score_drop'}]
    )
    reasons = {t['alpha_id']: t['reason'] for t in tasks}
    assert 'lifecycle_demoted' == reasons['alpha_1']
    assert reasons['alpha_2'].startswith('decay:')
