from diversification_filter import DiversificationFilterV1


def test_diversification_filter_blocks_second_family_promotion():
    alpha_defs = [
        {'alpha_id': 'alpha_1', 'signal_template_family': 'breakout'},
        {'alpha_id': 'alpha_2', 'signal_template_family': 'breakout'},
    ]
    decisions = [
        {'alpha_id': 'alpha_1', 'current_state': 'validated', 'target_state': 'promoted'},
        {'alpha_id': 'alpha_2', 'current_state': 'validated', 'target_state': 'promoted'},
    ]
    filtered = DiversificationFilterV1({'max_active_per_family': 1, 'promotion_targets': {'promoted', 'active'}, 'active_states': {'promoted', 'shadow', 'active'}}).filter_decisions(alpha_defs, decisions, current_states={})
    assert filtered[0]['diversification_pass'] is True
    assert filtered[1]['diversification_pass'] is False
    assert filtered[1]['target_state'] == 'validated'
