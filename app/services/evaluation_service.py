from datetime import datetime, timezone
from statistics import mean
from app.models.evaluation import EvaluationRun, EvaluationCaseResult, QualityMetricSnapshot, ImprovementExperiment
from app.schemas.evaluation import *

class EvaluationNotFoundError(Exception): pass
class ExperimentNotFoundError(Exception): pass

class EvaluationService:
    def __init__(self, repository): self.repository=repository

    def create_run(self, request: EvaluationRunCreate) -> EvaluationRunResponse:
        now=datetime.now(timezone.utc)
        results=[]
        for case in request.cases:
            passed, reason=self._compare(case.expected, case.actual, case.score, request.thresholds)
            results.append(EvaluationCaseResult(case_id=case.case_id,expected=case.expected,actual=case.actual,passed=passed,score=case.score,failure_reason=reason,latency_ms=case.latency_ms,cost_usd=case.cost_usd))
        metrics=self._metrics(results)
        run=EvaluationRun(name=request.name,component=request.component.value,dataset_version=request.dataset_version,system_version=request.system_version,status="completed",total_cases=len(results),passed_cases=sum(x.passed for x in results),metrics=metrics,thresholds=request.thresholds,notes=request.notes,started_at=now,completed_at=now)
        return self._run_response(self.repository.save_run(run,results), results)

    def get_run(self, run_id):
        run=self.repository.get_run(run_id)
        if not run: raise EvaluationNotFoundError(run_id)
        return self._run_response(run,self.repository.case_results(run_id))

    def list_runs(self, component=None, limit=20):
        return [self._run_response(x,[]) for x in self.repository.list_runs(component.value if component else None,limit)]

    def save_metric(self, request):
        item=QualityMetricSnapshot(component=request.component.value,metric_name=request.metric_name,metric_value=request.metric_value,numerator=request.numerator,denominator=request.denominator,period_start=request.period_start,period_end=request.period_end,metadata_json=request.metadata)
        return self._metric_response(self.repository.upsert_metric(item))

    def metric_history(self, component, metric_name=None, limit=100):
        return [self._metric_response(x) for x in self.repository.metrics(component.value,metric_name,limit)]

    def create_experiment(self, request):
        item=ImprovementExperiment(name=request.name,component=request.component.value,hypothesis=request.hypothesis,control_version=request.control_version,treatment_version=request.treatment_version,primary_metric=request.primary_metric,status="running",allocation_percent=request.allocation_percent,guardrails=request.guardrails,result={})
        return self._experiment_response(self.repository.save_experiment(item))

    def complete_experiment(self, experiment_id, request):
        item=self.repository.get_experiment(experiment_id)
        if not item: raise ExperimentNotFoundError(experiment_id)
        lift=request.treatment_metric-request.control_metric
        decision="rollback" if request.guardrail_violations else ("promote" if lift>0 else "keep_control")
        item.status="completed"; item.result={"control_metric":request.control_metric,"treatment_metric":request.treatment_metric,"absolute_lift":round(lift,6),"relative_lift":round(lift/request.control_metric,6) if request.control_metric else None,"sample_size_control":request.sample_size_control,"sample_size_treatment":request.sample_size_treatment,"guardrail_violations":request.guardrail_violations,"notes":request.notes}; item.decision=decision; item.completed_at=datetime.now(timezone.utc)
        return self._experiment_response(self.repository.commit(item))

    @staticmethod
    def _compare(expected,actual,score,thresholds):
        mismatches=[k for k,v in expected.items() if actual.get(k)!=v]
        minimum=thresholds.get("minimum_case_score")
        if minimum is not None and (score is None or score<minimum): mismatches.append("score_below_threshold")
        return (not mismatches, None if not mismatches else "Mismatch: "+", ".join(mismatches))

    @staticmethod
    def _metrics(results):
        total=len(results); lat=[x.latency_ms for x in results if x.latency_ms is not None]; costs=[x.cost_usd for x in results if x.cost_usd is not None]; scores=[x.score for x in results if x.score is not None]
        return {"pass_rate":round(sum(x.passed for x in results)/total,4),"mean_score":round(mean(scores),4) if scores else 0.0,"mean_latency_ms":round(mean(lat),2) if lat else 0.0,"total_cost_usd":round(sum(costs),6) if costs else 0.0}

    @staticmethod
    def _run_response(x,cases):
        return EvaluationRunResponse(id=x.id,name=x.name,component=x.component,dataset_version=x.dataset_version,system_version=x.system_version,status=x.status,total_cases=x.total_cases,passed_cases=x.passed_cases,metrics=x.metrics,thresholds=x.thresholds,cases=[EvaluationCaseResponse(case_id=c.case_id,passed=c.passed,score=c.score,failure_reason=c.failure_reason,latency_ms=c.latency_ms,cost_usd=c.cost_usd) for c in cases],created_at=x.created_at,completed_at=x.completed_at)
    @staticmethod
    def _metric_response(x):
        return MetricSnapshotResponse(id=x.id,component=x.component,metric_name=x.metric_name,metric_value=x.metric_value,numerator=x.numerator,denominator=x.denominator,period_start=x.period_start,period_end=x.period_end,metadata=x.metadata_json,created_at=x.created_at)
    @staticmethod
    def _experiment_response(x):
        return ExperimentResponse(id=x.id,name=x.name,component=x.component,hypothesis=x.hypothesis,control_version=x.control_version,treatment_version=x.treatment_version,primary_metric=x.primary_metric,status=x.status,allocation_percent=x.allocation_percent,guardrails=x.guardrails,result=x.result,decision=x.decision,created_at=x.created_at,completed_at=x.completed_at)
