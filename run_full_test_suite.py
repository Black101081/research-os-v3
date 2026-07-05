from pathlib import Path
import json
import subprocess
import sys

BASE = Path(__file__).resolve().parent
result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(BASE / 'tests'), '-v'], capture_output=True, text=True)
summary = {
    'returncode': result.returncode,
    'stdout': result.stdout,
    'stderr': result.stderr,
    'status': 'pass' if result.returncode == 0 else 'fail',
}
runtime = BASE / 'runtime'
runtime.mkdir(exist_ok=True)
(runtime / 'test_report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
md = '# Full Test Suite Report\n\n```text\n' + result.stdout + '\n' + result.stderr + '\n```\n'
(runtime / 'test_report.md').write_text(md, encoding='utf-8')
print(json.dumps({'status': summary['status'], 'returncode': result.returncode}))
