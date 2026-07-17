# Level 6 API Examples

## Create evaluation run
```json
POST /api/v1/evaluation/runs
{
  "name": "Diagnostic regression",
  "component": "diagnostic",
  "dataset_version": "eval-v1",
  "system_version": "diagnostic-v1",
  "thresholds": {"minimum_case_score": 0.8},
  "cases": [{
    "case_id": "case-001",
    "expected": {"error_category": "procedural_error"},
    "actual": {"error_category": "procedural_error"},
    "score": 0.95,
    "latency_ms": 450,
    "cost_usd": 0.003
  }]
}
```

## Record quality metric
```json
POST /api/v1/evaluation/metrics
{
  "component": "tutor",
  "metric_name": "helpfulness_rate",
  "metric_value": 0.82,
  "numerator": 82,
  "denominator": 100,
  "period_start": "2026-07-01",
  "period_end": "2026-07-07",
  "metadata": {"source": "tutor_feedback"}
}
```

## Create experiment
```json
POST /api/v1/evaluation/experiments
{
  "name": "Shorter Socratic hint prompt",
  "component": "tutor",
  "hypothesis": "A shorter hint prompt improves student helpfulness ratings.",
  "control_version": "tutor-v1",
  "treatment_version": "tutor-v2",
  "primary_metric": "helpfulness_rate",
  "allocation_percent": 50,
  "guardrails": {"maximum_latency_ms": 2000}
}
```
