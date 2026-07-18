import pytest

from tests.auth_test_helpers import auth_headers, register_and_login


@pytest.fixture
def admin(client):
    _, token = register_and_login(client, "evaluation-admin@example.com", role="admin")
    return auth_headers(token)


def test_evaluation_run_computes_metrics(client, admin):
    payload={"name":"Diagnostic regression","component":"diagnostic","dataset_version":"eval-v1","system_version":"diagnostic-v1",
    "thresholds":{"minimum_case_score":0.8},"cases":[
      {"case_id":"c1","expected":{"category":"arithmetic_error"},"actual":{"category":"arithmetic_error"},"score":0.95,"latency_ms":100,"cost_usd":0.01},
      {"case_id":"c2","expected":{"category":"procedural_error"},"actual":{"category":"arithmetic_error"},"score":0.7,"latency_ms":200,"cost_usd":0.02}]}
    r=client.post("/api/v1/evaluation/runs",json=payload,headers=admin)
    assert r.status_code==201
    b=r.json(); assert b["total_cases"]==2 and b["passed_cases"]==1
    assert b["metrics"]["pass_rate"]==0.5 and len(b["cases"])==2
    fetched=client.get(f"/api/v1/evaluation/runs/{b['id']}",headers=admin)
    assert fetched.status_code==200 and fetched.json()["id"]==b["id"]

def test_metric_snapshot_is_idempotent(client, admin):
    payload={"component":"tutor","metric_name":"helpfulness_rate","metric_value":0.8,"numerator":8,"denominator":10,"period_start":"2026-07-01","period_end":"2026-07-07","metadata":{"source":"feedback"}}
    first=client.post("/api/v1/evaluation/metrics",json=payload,headers=admin); assert first.status_code==201
    payload["metric_value"]=0.9
    second=client.post("/api/v1/evaluation/metrics",json=payload,headers=admin); assert second.status_code==201
    history=client.get("/api/v1/evaluation/metrics/tutor?metric_name=helpfulness_rate",headers=admin)
    assert history.status_code==200 and len(history.json())==1 and history.json()[0]["metric_value"]==0.9

def test_experiment_promotes_only_without_guardrail_violation(client, admin):
    exp=client.post("/api/v1/evaluation/experiments",json={"name":"Tutor prompt v2","component":"tutor","hypothesis":"A shorter hint prompt improves helpfulness.","control_version":"v1","treatment_version":"v2","primary_metric":"helpfulness_rate","allocation_percent":50,"guardrails":{"max_latency_ms":2000}},headers=admin)
    assert exp.status_code==201
    done=client.post(f"/api/v1/evaluation/experiments/{exp.json()['id']}/complete",json={"control_metric":0.7,"treatment_metric":0.78,"sample_size_control":100,"sample_size_treatment":100,"guardrail_violations":[]},headers=admin)
    assert done.status_code==200 and done.json()["decision"]=="promote"

def test_missing_run_returns_typed_404(client, admin):
    r=client.get("/api/v1/evaluation/runs/missing",headers=admin)
    assert r.status_code==404 and r.json()["error"]["code"]=="EVALUATION_RUN_NOT_FOUND"

def test_non_admin_is_rejected(client):
    _, token = register_and_login(client, "evaluation-student@example.com")
    r = client.get("/api/v1/evaluation/runs", headers=auth_headers(token))
    assert r.status_code==403
    assert r.json()["error"]["code"]=="ACCESS_DENIED"

def test_unauthenticated_is_rejected(client):
    r = client.get("/api/v1/evaluation/runs")
    assert r.status_code==401
    assert r.json()["error"]["code"]=="INVALID_TOKEN"
