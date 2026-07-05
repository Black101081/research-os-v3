# Sandbox Test Report

- Project root: /home/user/output/research_os_v3
- Python files: 22
- Detected test files: 6
- Smoke candidates: 6
- Overall status: FAIL

## Core checks
- syntax_compile: PASS (returncode=0)
  - stdout: Listing '/home/user/output/research_os_v3'... Listing '/home/user/output/research_os_v3/live_integration_test_v1'... Listing '/home/user/output/research_os_v3/live_integration_test_v2'... Listing '/home/user/output/research_os_v3/live_integration_test_v3'... Listing '/home/user/output/research_os_v3/live_integration_test_v4'... Listing '/home/user/output/research_os_v3/research_knowledge'... Compiling '/home/user/output/research_os_v3/research_knowledge/validator_runner.py'... Compiling '/home/user/output/research_os_v3/run_full_test_suite.py'... Listing '/home/user/output/research_os_v3/runtime'... Listing '/home/user/output/research_os_v3/runtime_test'... Listing '/home/user/output/research_os_v3/runtime_test_success'... Listing '/home/user/output/research_os_v3/sandbox_test_reports'... 
- validator_runner: PASS (returncode=0)
  - stdout: {   "indicator_total": 50,   "indicator_decisions": {     "PASS": 50   },   "indicator_avg_score": 90.0,   "strategy_total": 8,   "strategy_decisions": {     "PASS": 8   },   "strategy_avg_score": 100.0,   "top_indicator_issues": {     "missing_template:nearest_indicators": 50,     "neighbor_resolution_pending": 50   },   "top_strategy_issues": {     "none": 8   } } 
- pytest: PASS (returncode=0)
  - stdout: atetime.UTC).     'spec_id': f"{signal_name}-{symbol}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",  tests/test_engine_pipeline.py::EnginePipelineTests::test_full_pipeline_generates_strategy_spec_when_signal_active tests/test_integration_flow.py::IntegrationFlowTests::test_paper_replay_generates_strategy_spec_and_packet tests/test_regression_contracts.py::RegressionContractTests::test_playbook_packet_contract_fields_exist tests/test_regression_contracts.py::RegressionContractTests::test_strategy_spec_contract_fields_exist   /home/user/output/research_os_v3/strategy_spec_builder.py:14: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).     

## CLI smoke checks
- baseline_backtest_runner.py: PASS (returncode=0)
- tests/test_api_surface.py: FAIL (returncode=1)
  - stderr: Traceback (most recent call last):   File "/home/user/output/research_os_v3/tests/test_api_surface.py", line 3, in <module>     import app ModuleNotFoundError: No module named 'app' 
- tests/test_api_surfaces.py: FAIL (returncode=1)
  - stderr: Traceback (most recent call last):   File "/home/user/output/research_os_v3/tests/test_api_surfaces.py", line 5, in <module>     import app as app_module ModuleNotFoundError: No module named 'app' 
- tests/test_integration_flow.py: FAIL (returncode=1)
  - stderr: Traceback (most recent call last):   File "/home/user/output/research_os_v3/tests/test_integration_flow.py", line 5, in <module>     from bootstrap_ohlcv import warmup_engine ModuleNotFoundError: No module named 'bootstrap_ohlcv' 
- tests/test_regression_contracts.py: FAIL (returncode=1)
  - stderr: Traceback (most recent call last):   File "/home/user/output/research_os_v3/tests/test_regression_contracts.py", line 5, in <module>     from paper_replay import run_paper_replay_demo ModuleNotFoundError: No module named 'paper_replay' 
- tests/test_research_regression.py: FAIL (returncode=1)
  - stderr: Traceback (most recent call last):   File "/home/user/output/research_os_v3/tests/test_research_regression.py", line 5, in <module>     from backtest_bridge import build_bridge_demo ModuleNotFoundError: No module named 'backtest_bridge' 