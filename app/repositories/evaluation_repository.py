from sqlalchemy import select
from app.models.evaluation import EvaluationRun, EvaluationCaseResult, QualityMetricSnapshot, ImprovementExperiment

class EvaluationRepository:
    def __init__(self, db): self.db = db
    def save_run(self, run, cases):
        self.db.add(run); self.db.flush()
        for case in cases:
            case.run_id = run.id
            self.db.add(case)
        self.db.commit(); self.db.refresh(run); return run
    def get_run(self, run_id):
        return self.db.get(EvaluationRun, run_id)
    def case_results(self, run_id):
        return list(self.db.scalars(select(EvaluationCaseResult).where(EvaluationCaseResult.run_id==run_id).order_by(EvaluationCaseResult.case_id)).all())
    def list_runs(self, component=None, limit=20):
        q=select(EvaluationRun)
        if component: q=q.where(EvaluationRun.component==component)
        return list(self.db.scalars(q.order_by(EvaluationRun.created_at.desc()).limit(limit)).all())
    def upsert_metric(self, item):
        existing=self.db.scalar(select(QualityMetricSnapshot).where(
            QualityMetricSnapshot.component==item.component,
            QualityMetricSnapshot.metric_name==item.metric_name,
            QualityMetricSnapshot.period_start==item.period_start,
            QualityMetricSnapshot.period_end==item.period_end))
        if existing:
            for n in ["metric_value","numerator","denominator","metadata_json"]: setattr(existing,n,getattr(item,n))
            self.db.commit(); self.db.refresh(existing); return existing
        self.db.add(item); self.db.commit(); self.db.refresh(item); return item
    def metrics(self, component, metric_name=None, limit=100):
        q=select(QualityMetricSnapshot).where(QualityMetricSnapshot.component==component)
        if metric_name: q=q.where(QualityMetricSnapshot.metric_name==metric_name)
        return list(self.db.scalars(q.order_by(QualityMetricSnapshot.period_start.desc()).limit(limit)).all())
    def save_experiment(self, item):
        self.db.add(item); self.db.commit(); self.db.refresh(item); return item
    def get_experiment(self, experiment_id): return self.db.get(ImprovementExperiment, experiment_id)
    def commit(self, item): self.db.add(item); self.db.commit(); self.db.refresh(item); return item
