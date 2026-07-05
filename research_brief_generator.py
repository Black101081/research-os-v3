from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchBriefGeneratorV1:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _top_ranked(self, scorecards: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        ranked = sorted(scorecards, key=lambda x: (x.get('research_rank', 10**9), -float(x.get('research_score', 0.0) or 0.0)))
        return ranked[:limit]

    def _latest_events(self, lifecycle_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for row in lifecycle_events:
            latest[row['alpha_id']] = row
        return latest

    def build_brief_payload(self, registry: Any) -> Dict[str, Any]:
        scorecards = list(registry.validation_scorecards)
        lifecycle_events = list(registry.lifecycle_events)
        decay_profiles = list(registry.decay_profiles)
        revalidation_tasks = getattr(registry, 'revalidation_tasks', [])
        latest_events = self._latest_events(lifecycle_events)
        top_ranked = self._top_ranked(scorecards)
        promoted = [e for e in lifecycle_events if e.get('new_state') == 'promoted']
        demoted = [e for e in lifecycle_events if e.get('new_state') == 'demoted']
        quarantined = [e for e in lifecycle_events if e.get('new_state') == 'quarantined']
        decay_flagged = [d for d in decay_profiles if d.get('decay_flag')]
        return {
            'generated_at': now_iso(),
            'alpha_count': len(registry.alpha_definitions),
            'validation_scorecard_count': len(scorecards),
            'top_ranked_alphas': [
                {
                    'alpha_id': row.get('alpha_id'),
                    'research_rank': row.get('research_rank'),
                    'research_score': row.get('research_score'),
                    'validation_status': row.get('validation_status'),
                    'sample_window': row.get('sample_window'),
                }
                for row in top_ranked
            ],
            'latest_lifecycle_by_alpha': latest_events,
            'promoted_count': len(promoted),
            'demoted_count': len(demoted),
            'quarantined_count': len(quarantined),
            'decay_flag_count': len(decay_flagged),
            'revalidation_task_count': len(revalidation_tasks),
            'revalidation_tasks': revalidation_tasks,
        }

    def render_markdown(self, payload: Dict[str, Any]) -> str:
        lines = [
            '# Research Brief v1',
            '',
            f"Generated at: {payload['generated_at']}",
            f"Alpha count: {payload['alpha_count']}",
            f"Validation scorecards: {payload['validation_scorecard_count']}",
            f"Promoted: {payload['promoted_count']}",
            f"Demoted: {payload['demoted_count']}",
            f"Quarantined: {payload['quarantined_count']}",
            f"Decay flagged: {payload['decay_flag_count']}",
            f"Revalidation tasks: {payload['revalidation_task_count']}",
            '',
            '## Top Ranked',
            ''
        ]
        for row in payload['top_ranked_alphas']:
            lines.append(f"- {row['alpha_id']}: rank={row['research_rank']}, score={row['research_score']}, status={row['validation_status']}, sample={row['sample_window']}")
        lines.extend(['', '## Revalidation Tasks', ''])
        for task in payload['revalidation_tasks']:
            lines.append(f"- {task['alpha_id']}: {task['reason']} (priority={task['priority']}, due_hours={task['due_hours']})")
        if not payload['revalidation_tasks']:
            lines.append('- none')
        return "\n".join(lines) + "\n"

    def write_brief(self, registry: Any, stem: str = 'research_brief_v1') -> Dict[str, str]:
        payload = self.build_brief_payload(registry)
        json_path = self.output_dir / f'{stem}.json'
        md_path = self.output_dir / f'{stem}.md'
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        md_path.write_text(self.render_markdown(payload), encoding='utf-8')
        return {'json_path': str(json_path), 'md_path': str(md_path)}


def generate_playbook_code(symbol: str, strategy_name: str, parameters: dict, risk_limit: dict) -> str:
    class_name = "".join(x.title() for x in strategy_name.split("_")) + "Playbook"
    
    param_lines = []
    for k, v in parameters.items():
        param_lines.append(f"        self.{k} = {repr(v)}")
        
    risk_lines = []
    for k, v in risk_limit.items():
        risk_lines.append(f"        self.{k} = {repr(v)}")
        


    # Dynamic evaluation logic based on strategy_name
    if strategy_name == "macd_trend_continuation":
        evaluate_body = '''        macd = indicators.get("MACD")
        macd_sig = indicators.get("MACD_signal")
        if macd is None or macd_sig is None:
            return 0
            
        if macd > macd_sig:
            return 1
        elif macd < macd_sig:
            return -1
        return 0'''
    elif strategy_name == "bollinger_bands_reversion":
        evaluate_body = '''        close = bars[-1].close if bars else 0.0
        upper = indicators.get("BBANDS_upper", 0.0)
        lower = indicators.get("BBANDS_lower", 0.0)
        if not upper or not lower:
            return 0
            
        if close > upper:
            return -1  # overbought, short reversion
        elif close < lower:
            return 1   # oversold, long reversion
        return 0'''
    elif strategy_name == "bollinger_squeeze_breakout":
        evaluate_body = '''        width = indicators.get("BollingerWidth", 1.0)
        close = bars[-1].close if bars else 0.0
        mid = indicators.get("BBANDS_mid", 0.0)
        
        # Check squeeze threshold
        width_threshold = getattr(self, "width_threshold", 0.015)
        if width < width_threshold:
            # Squeeze is active, trigger on breakout
            if close > mid:
                return 1
            elif close < mid:
                return -1
        return 0'''
    else:
        evaluate_body = '''        # Default mock signal logic
        zscore = indicators.get("ZScore_Close", 0.0)
        if zscore > 2.0:
            return -1
        elif zscore < -2.0:
            return 1
        return 0'''

    code = f'''"""
Production Playbook generated by Research OS V3.
Generated at: {datetime.now().isoformat()}
Asset: {symbol}
Strategy: {strategy_name}
"""

class {class_name}:
    def __init__(self):
        self.symbol = "{symbol}"
        # Strategy Parameters
{chr(10).join(param_lines)}

        # Risk and Gating Limits
{chr(10).join(risk_lines)}

    def evaluate(self, bars, factors, indicators) -> int:
        """
        Evaluate real-time signals.
        Returns:
            1  for BUY/LONG
            -1 for SELL/SHORT
            0  for NEUTRAL
        """
{evaluate_body}
'''
    return code
