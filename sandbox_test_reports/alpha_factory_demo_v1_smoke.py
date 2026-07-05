import json, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from alpha_factory_demo_v1 import run_alpha_factory_demo_v1
payload = run_alpha_factory_demo_v1(root / 'sandbox_test_reports' / 'alpha_factory_demo_v1_run', candidate_limit=3)
print(json.dumps(payload['summary'], ensure_ascii=False))
