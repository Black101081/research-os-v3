import json
from pathlib import Path
from signal_generator import SignalGenerator
from candidate_pruner import CandidatePruner


def test_signal_generator_produces_candidates():
    root = Path(__file__).resolve().parents[1]
    factor_catalog = json.loads((root / 'factor_catalog_v1.json').read_text(encoding='utf-8'))
    template_library = json.loads((root / 'signal_template_library_v1.json').read_text(encoding='utf-8'))
    candidates = SignalGenerator(factor_catalog, template_library).generate_candidates()
    assert candidates
    assert all(c['validation_status'] == 'draft' for c in candidates)


def test_candidate_pruner_drops_duplicates():
    candidates = [
        {'trigger_definition': 'A > 1'},
        {'trigger_definition': 'A > 1'},
        {'trigger_definition': 'B < 2'},
    ]
    kept, dropped = CandidatePruner().prune(candidates)
    assert len(kept) == 2
    assert len(dropped) == 1
