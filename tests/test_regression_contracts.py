import json
import unittest
from pathlib import Path

from paper_replay import run_paper_replay_demo


class RegressionContractTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).resolve().parent.parent / 'config.example.json').read_text())

    def test_strategy_spec_contract_fields_exist(self):
        result = run_paper_replay_demo(self.config)
        spec = result['strategy_specs'][0]
        required = ['spec_version', 'spec_id', 'created_at', 'symbol', 'signal_name', 'signal_family', 'thesis', 'regime_at_creation', 'factor_snapshot', 'indicator_snapshot', 'execution_assumptions', 'risk_logic', 'status', 'next_stage']
        for key in required:
            self.assertIn(key, spec)

    def test_playbook_packet_contract_fields_exist(self):
        result = run_paper_replay_demo(self.config)
        packet = result['playbook_packets'][0]
        required = ['packet_version', 'created_at', 'spec_id', 'signal_name', 'symbol', 'current_stage', 'allowed_next_stage', 'research_status', 'decision_state', 'stage_checklist', 'strategy_spec']
        for key in required:
            self.assertIn(key, packet)
        self.assertEqual(packet['current_stage'], 'intake_and_hypothesis')

if __name__ == '__main__':
    unittest.main()
