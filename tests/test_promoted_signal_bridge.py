from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from promoted_signal_bridge import PromotedSignalBridge
from signal_orchestrator import safe_eval_expression, evaluate_supported_signals


class TestPromotedSignalBridge(unittest.TestCase):
    def test_safe_eval_expression(self):
        context = {
            'BollingerWidth': 0.02,
            'live_ret_from_last_close': 0.002,
            'zscore_close_20': -1.8,
            'micro_volatility_20': 0.003,
            'MACD': 0.5,
            'MACD_signal': 0.2,
        }
        
        # True cases
        self.assertTrue(safe_eval_expression("BollingerWidth < 0.03 and live_ret_from_last_close > 0.001", context))
        self.assertTrue(safe_eval_expression("zscore_close_20 < -1.5 and micro_volatility_20 < 0.004", context))
        self.assertTrue(safe_eval_expression("MACD > MACD_signal", context))
        
        # False cases
        self.assertFalse(safe_eval_expression("BollingerWidth > 0.03", context))
        
        # Unsafe string rejection
        self.assertFalse(safe_eval_expression("__import__('os').system('ls')", context))
        self.assertFalse(safe_eval_expression("eval('1+1')", context))

    def test_bridge_load_promoted_alphas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create dummy alpha definitions
            defn_path = tmp_path / 'alpha_definitions.jsonl'
            with defn_path.open('w', encoding='utf-8') as f:
                f.write(json.dumps({'alpha_id': 'alpha_1', 'alpha_name': 'test_breakout', 'signal_expression': 'A > 1', 'signal_template_family': 'breakout', 'regime_scope': ['uptrend']}) + '\n')
                f.write(json.dumps({'alpha_id': 'alpha_2', 'alpha_name': 'test_reversion', 'signal_expression': 'B < 2', 'signal_template_family': 'mean_reversion', 'regime_scope': ['range_chop']}) + '\n')
                
            # Create dummy lifecycle events
            evt_path = tmp_path / 'lifecycle_events.jsonl'
            with evt_path.open('w', encoding='utf-8') as f:
                # alpha_1 is promoted
                f.write(json.dumps({'alpha_id': 'alpha_1', 'target_state': 'promoted'}) + '\n')
                # alpha_2 is demoted
                f.write(json.dumps({'alpha_id': 'alpha_2', 'target_state': 'demoted'}) + '\n')
                
            bridge = PromotedSignalBridge(store_base=tmp_path)
            promoted = bridge.load_promoted_alphas()
            
            self.assertEqual(len(promoted), 1)
            self.assertEqual(promoted[0]['alpha_id'], 'alpha_1')
            self.assertEqual(promoted[0]['alpha_name'], 'test_breakout')


if __name__ == '__main__':
    unittest.main()
