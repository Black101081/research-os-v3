from signal_generator import SignalGenerator
from validation_runner import ValidationRunnerV1
import json
from pathlib import Path


def test_validation_runner_scores_generated_candidates():
    root = Path(__file__).resolve().parents[1]
    factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()
    runner = ValidationRunnerV1()
    scorecards = runner.validate_candidates(candidates)
    assert scorecards
    assert all('research_score' in row for row in scorecards)
    assert all('validation_status' in row for row in scorecards)
