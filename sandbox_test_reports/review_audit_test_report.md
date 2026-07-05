# Review Audit Test Report

Repo root: /home/user/output/research_os_v3
Top-level Python modules: 34
Compile returncode: 0
Pytest returncode: 0
Demo returncode: 0

## Pytest tail
```
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33m                              [100%][0m
[33m=============================== warnings summary ===============================[0m
app.py:82
  /home/user/output/research_os_v3/app.py:82: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event('startup')

../../../../usr/local/lib/python3.12/site-packages/fastapi/applications.py:4495
../../../../usr/local/lib/python3.12/site-packages/fastapi/applications.py:4495
  /usr/local/lib/python3.12/site-packages/fastapi/applications.py:4495: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

app.py:98
  /home/user/output/research_os_v3/app.py:98: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event('shutdown')

tests/test_engine_pipeline.py::EnginePipelineTests::test_full_pipeline_generates_strategy_spec_when_signal_active
tests/test_integration_flow.py::IntegrationFlowTests::test_paper_replay_generates_strategy_spec_and_packet
tests/test_regression_contracts.py::RegressionContractTests::test_playbook_packet_contract_fields_exist
tests/test_regression_contracts.py::RegressionContractTests::test_strategy_spec_contract_fields_exist
  /home/user/output/research_os_v3/strategy_spec_builder.py:15: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    'spec_id': f"{signal_name}-{symbol}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",

tests/test_engine_pipeline.py::EnginePipelineTests::test_full_pipeline_generates_strategy_spec_when_signal_active
tests/test_integration_flow.py::IntegrationFlowTests::test_paper_replay_generates_strategy_spec_and_packet
tests/test_regression_contracts.py::RegressionContractTests::test_playbook_packet_contract_fields_exist
tests/test_regression_contracts.py::RegressionContractTests::test_strategy_spec_contract_fields_exist
  /home/user/output/research_os_v3/strategy_spec_builder.py:16: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    'created_at': datetime.utcnow().isoformat(),

tests/test_engine_pipeline.py::EnginePipelineTests::test_full_pipeline_generates_strategy_spec_when_signal_active
tests/test_integration_flow.py::IntegrationFlowTests::test_paper_replay_generates_strategy_spec_and_packet
tests/test_regression_contracts.py::RegressionContractTests::test_playbook_packet_contract_fields_exist
tests/test_regression_contracts.py::RegressionContractTests::test_strategy_spec_contract_fields_exist
  /home/user/output/research_os_v3/playbook_bridge.py:22: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    'created_at': datetime.utcnow().isoformat(),

tests/test_engine_pipeline.py::EnginePipelineTests::test_registry_writes_snapshot_specs_and_packets
  /home/user/output/research_os_v3/registry_writer.py:19: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    payload = {'ts': datetime.utcnow().isoformat(), 'snapshot': snapshot}

tests/test_engine_pipeline.py::EnginePipelineTests::test_registry_writes_snapshot_specs_and_packets
  /home/user/output/research_os_v3/registry_writer.py:23: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    ts = datetime.utcnow().isoformat()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
[33m[32m43 passed[0m, [33m[1m18 warnings[0m[33m in 0.70s[0m[0m


```

## Demo stdout
```
{
  "candidate_count": 3,
  "registered_alpha_count": 3,
  "validation_scorecard_count": 4,
  "top_ranked_alpha": "alpha_1",
  "top_research_score": 127.4135,
  "promoted_count": 3,
  "demoted_count": 0,
  "quarantined_count": 0,
  "decay_profile_count": 1,
  "revalidation_task_count": 1,
  "brief_json_path": "/home/user/output/research_os_v3/sandbox_test_reports/audit_demo_run/registry_store/briefs/alpha_factory_demo_v1_brief.json",
  "brief_md_path": "/home/user/output/research_os_v3/sandbox_test_reports/audit_demo_run/registry_store/briefs/alpha_factory_demo_v1_brief.md",
  "healthcheck": {
    "alpha_count": 3,
    "validation_scorecard_count": 4,
    "latest_scorecard_count": 3,
    "lifecycle_event_count": 3,
    "decay_profile_count": 1,
    "revalidation_task_count": 1,
    "top_alpha_id": "alpha_3"
  }
}

```
